from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FORBIDDEN_LOG_KEYS = {"text", "prompt", "chunk", "content", "tenant_id", "output", "secret", "password", "token"}


@dataclass(frozen=True)
class SoakEvent:
    request_type: str
    route: str
    success: bool
    status_code: int
    latency_ms: float
    tenant_hash: str
    index_version: str
    provider_mode: str
    memory_rss_mb: float
    cpu_percent: float
    thread_count: int
    fd_count: int
    queue_depth: int
    cache_size: int
    error_code: str | None = None


class SoakEventWriter:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: SoakEvent) -> dict[str, Any]:
        row = {
            "event_id": uuid.uuid4().hex,
            "wall_time_utc": datetime.now(timezone.utc).isoformat(),
            "monotonic_ns": time.monotonic_ns(),
            **event.__dict__,
        }
        self._guard(row)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return row

    @staticmethod
    def tenant_hash(tenant_id: str) -> str:
        return hashlib.sha256(tenant_id.encode("utf-8", errors="replace")).hexdigest()[:24]

    @staticmethod
    def _guard(row: dict[str, Any]) -> None:
        for key, value in row.items():
            lowered_key = key.lower()
            if any(marker in lowered_key for marker in FORBIDDEN_LOG_KEYS):
                if key != "tenant_hash":
                    raise ValueError(f"SOAK_EVENT_FORBIDDEN_KEY:{key}")
            if isinstance(value, str):
                lowered_value = value.lower()
                if "d:\\e review" in lowered_value or "d:\\ereviewagent\\models" in lowered_value:
                    raise ValueError("SOAK_EVENT_ABSOLUTE_PATH_LEAK")


def resource_sample() -> dict[str, Any]:
    rss_mb = 0.0
    cpu = 0.0
    fd_count = 0
    try:
        import psutil

        process = psutil.Process(os.getpid())
        rss_mb = round(process.memory_info().rss / 1024 / 1024, 3)
        cpu = round(process.cpu_percent(interval=None), 3)
        try:
            fd_count = process.num_fds()
        except AttributeError:
            fd_count = process.num_handles()
    except Exception:
        pass
    return {
        "memory_rss_mb": rss_mb,
        "cpu_percent": cpu,
        "thread_count": threading.active_count(),
        "fd_count": fd_count,
    }
