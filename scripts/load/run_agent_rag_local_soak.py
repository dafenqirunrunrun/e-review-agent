from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-observability" / "local-soak-summary.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8008")
    parser.add_argument("--duration-sec", type=int, default=600)
    parser.add_argument("--interval-sec", type=float, default=5.0)
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()

    deadline = time.monotonic() + max(1, args.duration_sec)
    success = 0
    failures: list[str] = []
    latencies: list[float] = []
    idx = 0
    while time.monotonic() < deadline:
        try:
            latencies.append(call_analyze(args.base_url, idx))
            success += 1
        except Exception as exc:
            failures.append(str(exc)[:180])
        idx += 1
        if args.interval_sec > 0:
            time.sleep(args.interval_sec)

    summary = {
        "status": "PASS" if not failures and success > 0 else "FAIL",
        "durationSec": args.duration_sec,
        "intervalSec": args.interval_sec,
        "success": success,
        "failure": len(failures),
        "maxLatencyMs": max(latencies) if latencies else 0,
        "failures": failures[:5],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if summary["status"] == "PASS":
        print("AGENT_RAG_LOCAL_SOAK_PASS")
        return 0
    print("AGENT_RAG_LOCAL_SOAK_FAIL")
    print(json.dumps(summary, ensure_ascii=False))
    return 1


def call_analyze(base_url: str, idx: int) -> float:
    request_id = f"soak-{int(time.time() * 1000)}-{idx}"
    payload = {
        "requestId": request_id,
        "tenantId": "tenant-a",
        "subjectId": f"soak-review-{idx}",
        "query": "refund broken product" if idx % 2 == 0 else "normal positive review",
    }
    request = urllib.request.Request(
        base_url + "/api/v1/agent-rag/analyze",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Request-Id": request_id},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("requestId") != request_id:
        raise RuntimeError("REQUEST_ID_MISMATCH")
    return round((time.perf_counter() - started) * 1000, 3)


if __name__ == "__main__":
    raise SystemExit(main())
