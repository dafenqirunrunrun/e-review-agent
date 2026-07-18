from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass


FORBIDDEN_CACHE_MARKERS = {"ignore previous instructions", "api_key", "bearer ", "cookie:"}


def safe_cache_key(*, tenant_hash: str, model_version: str, index_version: str, prompt_version: str, normalized_query: str) -> str:
    material = json.dumps(
        {
            "tenant": tenant_hash,
            "model": model_version,
            "index": index_version,
            "prompt": prompt_version,
            "query": hashlib.sha256(normalized_query.encode("utf-8", errors="replace")).hexdigest(),
        },
        sort_keys=True,
    )
    return hashlib.sha256(material.encode()).hexdigest()


@dataclass
class TTLCache:
    ttl_seconds: int

    def __post_init__(self):
        self._values: dict[str, tuple[float, object]] = {}

    def put(self, key: str, value: object, source_text: str = "") -> bool:
        lowered = source_text.lower()
        if any(marker in lowered for marker in FORBIDDEN_CACHE_MARKERS):
            return False
        self._values[key] = (time.time() + self.ttl_seconds, value)
        return True

    def get(self, key: str) -> object | None:
        row = self._values.get(key)
        if not row:
            return None
        expires_at, value = row
        if expires_at < time.time():
            self._values.pop(key, None)
            return None
        return value
