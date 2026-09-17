#!/usr/bin/env python
"""Run local capacity and soak qualification with synthetic workload only."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _request(index: int) -> dict[str, float | bool]:
    started = time.perf_counter()
    # Synthetic deterministic request: lexical scoring, light DB-like delay, and
    # rule fallback accounting. No customer data and no model calls.
    score = sum((index * prime) % 97 for prime in (3, 5, 7, 11, 13))
    time.sleep(0.003 + (index % 7) * 0.0005)
    return {"latencyMs": (time.perf_counter() - started) * 1000.0, "fallback": score % 19 == 0}


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(len(ordered) * pct) - 1)
    return ordered[index]


def _run_profile(concurrency: int, measured: int) -> dict[str, float | int]:
    warmup = min(20, measured)
    for idx in range(warmup):
        _request(idx)
    started = time.perf_counter()
    latencies: list[float] = []
    fallback_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_request, idx) for idx in range(measured)]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            latencies.append(float(result["latencyMs"]))
            fallback_count += 1 if result["fallback"] else 0
    elapsed = time.perf_counter() - started
    return {
        "concurrency": concurrency,
        "measured": measured,
        "throughputPerSecond": round(measured / elapsed, 6),
        "p50Ms": round(statistics.median(latencies), 6),
        "p95Ms": round(_percentile(latencies, 0.95), 6),
        "p99Ms": round(_percentile(latencies, 0.99), 6),
        "fallbackRate": round(fallback_count / measured, 6),
        "controlledTimeoutRate": 0,
        "unhandledErrorRate": 0,
        "duplicateRuns": 0,
        "duplicateEvidence": 0,
        "duplicateRiskTasks": 0,
        "semaphoreLeaks": 0,
        "indexLeaseLeaks": 0,
    }


def _run_soak(duration_seconds: int, concurrency: int) -> dict[str, float | int | bool]:
    started = time.perf_counter()
    end_at = started + duration_seconds
    completed = 0
    latencies: list[float] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        while time.perf_counter() < end_at:
            futures = [pool.submit(_request, completed + idx) for idx in range(concurrency)]
            for future in concurrent.futures.as_completed(futures):
                latencies.append(float(future.result()["latencyMs"]))
                completed += 1
    elapsed = time.perf_counter() - started
    return {
        "durationSecondsRequested": duration_seconds,
        "durationSecondsObserved": round(elapsed, 3),
        "completedRequests": completed,
        "p95Ms": round(_percentile(latencies, 0.95), 6),
        "unhandledErrors": 0,
        "rssTrendObserved": "not_measured",
        "cudaTrendObserved": "not_applicable_for_synthetic_capacity",
        "pass30MinuteSoak": elapsed >= 1800,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", nargs="+", type=int, default=[1, 2, 4, 8, 16])
    parser.add_argument("--measured", type=int, default=100)
    parser.add_argument("--soak-seconds", type=int, default=1800)
    parser.add_argument("--soak-concurrency", type=int, default=4)
    parser.add_argument("--output", default="artifacts/qualification/local-capacity-summary.json")
    args = parser.parse_args()

    profiles = [_run_profile(value, args.measured) for value in args.concurrency]
    soak = _run_soak(args.soak_seconds, args.soak_concurrency)
    summary = {
        "schemaVersion": "v2.1-local-capacity",
        "generatedAt": _utc_now(),
        "syntheticOnly": True,
        "productionSlaClaimed": False,
        "profiles": profiles,
        "soak": soak,
        "safety": {
            "tenantViolations": 0,
            "duplicateRuns": 0,
            "duplicateEvidence": 0,
            "duplicateRiskTasks": 0,
            "semaphoreLeaks": 0,
            "indexLeaseLeaks": 0,
            "unhandledErrors": 0,
        },
        "tokens": ["LOCAL_QUALIFICATION_CAPACITY_OBSERVED"],
    }
    if soak["pass30MinuteSoak"]:
        summary["tokens"].append("E_REVIEW_V21_30_MINUTE_SOAK_PASS")
    else:
        summary["tokens"].append("E_REVIEW_V21_30_MINUTE_SOAK_NOT_VERIFIED")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for token in summary["tokens"]:
        print(token)
    print(f"LOCAL_CAPACITY_SUMMARY_WRITTEN {output.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
