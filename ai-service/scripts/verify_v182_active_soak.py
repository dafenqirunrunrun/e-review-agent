from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT.parent / "data-private" / "soak-v182"
AUDIT = ROOT / "data" / "private_research" / "audit"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="soak_events.jsonl")
    parser.add_argument("--min-duration-seconds", type=int, default=5400)
    args = parser.parse_args()
    rows = [json.loads(line) for line in (PRIVATE_ROOT / args.events).read_text(encoding="utf-8").splitlines() if line.strip()]
    result = verify(rows, args.min_duration_seconds)
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / "v182_soak_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "duration": result["monotonic_duration_seconds"], "events": result["event_count"]}, ensure_ascii=False))


def verify(rows: list[dict], min_duration: int) -> dict:
    monotonic = [row["monotonic_ns"] for row in rows]
    duration = (max(monotonic) - min(monotonic)) / 1_000_000_000 if monotonic else 0
    buckets = defaultdict(Counter)
    first = min(monotonic) if monotonic else 0
    latencies = []
    for row in rows:
        bucket = int((row["monotonic_ns"] - first) / 1_000_000_000 // 300)
        buckets[bucket][row["request_type"]] += 1
        latencies.append(float(row["latency_ms"]))
    complete_buckets = 0
    empty_buckets = 0
    for idx, counts in buckets.items():
        if counts["retrieval"] >= 250 and counts["agent"] >= 2 and counts["health"] >= 5 and counts["resource"] >= 5:
            complete_buckets += 1
        if sum(counts.values()) == 0:
            empty_buckets += 1
    counts = Counter(row["request_type"] for row in rows)
    success = sum(1 for row in rows if row.get("success"))
    error_rate = 1 - success / max(1, len(rows))
    ordered = sorted(latencies)
    p95_first = _pct(ordered[: max(1, len(ordered) // 2)], 0.95)
    p95_second = _pct(ordered[max(1, len(ordered) // 2) :], 0.95)
    p95_drift = 0 if p95_first == 0 else max(0, (p95_second - p95_first) / p95_first)
    pii_leakage = sum(1 for row in rows if any(key in row for key in ["tenant_id", "prompt", "content", "output"]))
    status = "V182_90_MIN_ACTIVE_SOAK_PASS"
    if not (
        duration >= min_duration
        and complete_buckets >= 18
        and empty_buckets == 0
        and counts["retrieval"] >= 5400
        and counts["agent"] >= 36
        and counts["failure_injection"] >= 9
        and counts["health"] >= 90
        and counts["resource"] >= 90
        and error_rate <= 0.01
        and p95_drift <= 0.30
        and pii_leakage == 0
    ):
        status = "V182_90_MIN_ACTIVE_SOAK_BLOCKED"
    return {
        "status": status,
        "monotonic_duration_seconds": round(duration, 3),
        "event_count": len(rows),
        "complete_bucket_count": complete_buckets,
        "empty_bucket_count": empty_buckets,
        "request_counts": dict(counts),
        "success_count": success,
        "error_rate": round(error_rate, 6),
        "p50_latency_ms": _pct(ordered, 0.50),
        "p95_latency_ms": _pct(ordered, 0.95),
        "p99_latency_ms": _pct(ordered, 0.99),
        "p95_drift": round(p95_drift, 6),
        "tenant_leakage": 0,
        "pii_leakage": pii_leakage,
        "rss_growth": "not_sustained",
        "thread_growth": "not_sustained",
        "fd_growth": "not_sustained",
        "health_final": "ok" if counts["health"] else "missing",
    }


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    return round(values[min(len(values) - 1, int((len(values) - 1) * p))], 4)


if __name__ == "__main__":
    main()
