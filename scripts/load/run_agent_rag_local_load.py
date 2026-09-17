from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-observability" / "local-load-summary.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8008")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()

    started = time.perf_counter()
    latencies: list[float] = []
    failures: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = [pool.submit(call_analyze, args.base_url, idx) for idx in range(args.requests)]
        for future in concurrent.futures.as_completed(futures):
            try:
                latencies.append(future.result())
            except Exception as exc:
                failures.append(str(exc)[:180])
    summary = {
        "status": "PASS" if len(failures) == 0 and len(latencies) >= args.requests else "FAIL",
        "requests": args.requests,
        "concurrency": args.concurrency,
        "success": len(latencies),
        "failure": len(failures),
        "durationSec": round(time.perf_counter() - started, 3),
        "latencyMs": latency_summary(latencies),
        "failures": failures[:5],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if summary["status"] == "PASS":
        print("AGENT_RAG_LOCAL_LOAD_PASS")
        return 0
    print("AGENT_RAG_LOCAL_LOAD_FAIL")
    print(json.dumps(summary, ensure_ascii=False))
    return 1


def call_analyze(base_url: str, idx: int) -> float:
    request_id = f"load-{int(time.time() * 1000)}-{idx}"
    payload = {
        "requestId": request_id,
        "tenantId": "tenant-a",
        "subjectId": f"load-review-{idx}",
        "query": "broken package refund after-sales risk" if idx % 3 == 0 else "normal delivery and acceptable quality",
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url + "/api/v1/agent-rag/analyze",
        data=body,
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("requestId") != request_id:
        raise RuntimeError("REQUEST_ID_MISMATCH")
    return round((time.perf_counter() - started) * 1000, 3)


def latency_summary(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "p50": 0, "p95": 0, "max": 0}
    ordered = sorted(values)
    return {
        "count": len(values),
        "p50": percentile(ordered, 0.50),
        "p95": percentile(ordered, 0.95),
        "max": max(values),
        "mean": round(statistics.mean(values), 3),
    }


def percentile(values: list[float], point: float) -> float:
    index = int(round((len(values) - 1) * point))
    return values[max(0, min(index, len(values) - 1))]


if __name__ == "__main__":
    raise SystemExit(main())
