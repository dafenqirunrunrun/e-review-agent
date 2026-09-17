from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import sys

AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.main import app
from app.observability.metrics import metrics_registry


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "private_research" / "audit" / "v180_performance_soak.json"
DOC = ROOT / "docs" / "enterprise" / "v180_performance_soak.md"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-seconds", type=int, default=30)
    parser.add_argument("--target-rps", type=float, default=2.0)
    args = parser.parse_args()
    result = run_soak(args.duration_seconds, args.target_rps)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    DOC.write_text(render_doc(result), encoding="utf-8", newline="\n")
    print(result["status"])
    if result["status"].endswith("_FAIL"):
        raise SystemExit(2)


def run_soak(duration_seconds: int, target_rps: float) -> dict[str, Any]:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    metrics_registry.reset()
    client = TestClient(app)
    interval = 1.0 / max(0.1, target_rps)
    deadline = time.perf_counter() + duration_seconds
    latencies: list[float] = []
    statuses: list[int] = []
    index = 0
    while time.perf_counter() < deadline:
        started = time.perf_counter()
        payload = {
            "request_id": f"v180-soak-{index}",
            "tenant_id": "tenant-alpha" if index % 2 == 0 else "tenant-beta",
            "review_text": "包装破损需要售后处理" if index % 3 else "普通好评, 使用正常",
            "rating": 1 if index % 3 else 5,
        }
        response = client.post("/api/v1/e-review/analyze", json=payload)
        statuses.append(response.status_code)
        latencies.append(round((time.perf_counter() - started) * 1000, 4))
        index += 1
        elapsed = time.perf_counter() - started
        if elapsed < interval:
            time.sleep(interval - elapsed)
    success = sum(1 for status in statuses if status == 200)
    error = len(statuses) - success
    p95 = percentile(latencies, 0.95)
    success_rate = success / max(1, len(statuses))
    status = "V180_PERFORMANCE_SMOKE_PASS_SOAK_PENDING"
    if duration_seconds >= 5400 and success_rate >= 0.99 and p95 <= 1000:
        status = "V180_90_MIN_SOAK_PASS"
    elif success_rate < 0.99:
        status = "V180_PERFORMANCE_SMOKE_FAIL"
    return {
        "status": status,
        "duration_seconds": duration_seconds,
        "target_rps": target_rps,
        "request_count": len(statuses),
        "success_count": success,
        "error_count": error,
        "success_rate": round(success_rate, 6),
        "latency_ms": {
            "min": round(min(latencies), 4) if latencies else 0,
            "max": round(max(latencies), 4) if latencies else 0,
            "avg": round(statistics.mean(latencies), 4) if latencies else 0,
            "p95": p95,
        },
        "metrics_snapshot": metrics_registry.snapshot(),
        "soak_90_min_required": True,
        "soak_90_min_completed": duration_seconds >= 5400,
        "closed_holdout_accessed": False,
        "training_executed": False,
    }


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * p)))
    return round(ordered[index], 4)


def render_doc(result: dict[str, Any]) -> str:
    if result["soak_90_min_completed"]:
        boundary = "This run completed the 5400-second soak threshold required by the v1.8 performance gate."
    else:
        boundary = "The current run is a short performance smoke. The v1.8 final readiness gate still requires a 90-minute soak."
    return f"""# v1.8.0 Performance and Soak

Status: `{result['status']}`

## Run

- Duration seconds: `{result['duration_seconds']}`
- Target RPS: `{result['target_rps']}`
- Request count: `{result['request_count']}`
- Success rate: `{result['success_rate']}`
- P95 latency ms: `{result['latency_ms']['p95']}`

## Boundary

{boundary}
"""


if __name__ == "__main__":
    main()
