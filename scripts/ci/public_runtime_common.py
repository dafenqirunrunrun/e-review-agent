from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = ROOT / "artifacts" / "runtime" / "v1.9.0-phase2"


class PublicRuntimeError(RuntimeError):
    pass


def env(name: str, default: str) -> str:
    return os.getenv(name, default).rstrip("/")


def backend_url() -> str:
    return env("PUBLIC_BACKEND_URL", "http://127.0.0.1:8080")


def ai_url() -> str:
    return env("PUBLIC_AI_URL", "http://127.0.0.1:8008")


def admin_url() -> str:
    return env("PUBLIC_ADMIN_URL", "http://127.0.0.1:8081")


def customer_url() -> str:
    return env("PUBLIC_CUSTOMER_URL", "http://127.0.0.1:8082")


def request_json(method: str, url: str, payload: Any | None = None, headers: dict[str, str] | None = None, timeout: int = 20) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})
    req = urllib.request.Request(url, data=body, method=method.upper(), headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read().decode("utf-8", errors="replace")
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as exc:
        data = exc.read().decode("utf-8", errors="replace")
        raise PublicRuntimeError(f"HTTP {exc.code} for {url}: {data[:500]}") from exc
    except Exception as exc:
        raise PublicRuntimeError(f"{type(exc).__name__} for {url}: {exc}") from exc


def request_text(url: str, timeout: int = 10) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.status >= 400:
                raise PublicRuntimeError(f"HTTP {response.status} for {url}")
            return response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise PublicRuntimeError(f"{type(exc).__name__} for {url}: {exc}") from exc


def assert_litemall_ok(response: dict, label: str) -> dict:
    if response.get("errno") != 0:
        raise PublicRuntimeError(f"{label} failed: {response}")
    data = response.get("data")
    return data if isinstance(data, dict) else {"value": data}


def wait_until(label: str, probe, timeout_seconds: int = 180, interval_seconds: float = 3.0) -> Any:
    deadline = time.time() + timeout_seconds
    last_error = None
    while time.time() < deadline:
        try:
            return probe()
        except Exception as exc:
            last_error = exc
            print(f"waiting for {label}: {exc}", flush=True)
            time.sleep(interval_seconds)
    raise PublicRuntimeError(f"Timed out waiting for {label}: {last_error}")


def write_evidence(name: str, payload: Any) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def run_command(args: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print("+ " + " ".join(args), flush=True)
    proc = subprocess.run(args, cwd=str(cwd or ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(proc.stdout, flush=True)
    if check and proc.returncode != 0:
        raise PublicRuntimeError(f"Command failed with exit {proc.returncode}: {' '.join(args)}")
    return proc


def main_guard(fn) -> None:
    try:
        fn()
    except Exception as exc:
        print(f"PUBLIC_RUNTIME_SCRIPT_FAILED: {exc}", file=sys.stderr)
        raise
