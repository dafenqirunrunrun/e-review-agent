from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-agent-trace-resource-result.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    jsonl = payload.get("modes", {}).get("jsonl", {})
    ok = (
        payload.get("jsonlP95LatencyRatio", 999) <= 20
        and payload.get("jsonlAbsoluteP95OverheadMs", 999) <= 50
        and jsonl.get("p95TraceSizeBytes", 999999) <= 128 * 1024
        and jsonl.get("traceWriteFailureCount") == 0
    )
    print("E_REVIEW_V24_AGENT_TRACE_RESOURCE_PASS" if ok else "TRACE_QUALITY_PASS_RESOURCE_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
