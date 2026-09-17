from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts" / "agent-productionization"


def main() -> int:
    integrity = json.loads((BASE / "v24-agent-trace-integrity-result.json").read_text(encoding="utf-8"))
    tamper = json.loads((BASE / "v24-agent-trace-tamper-detection.json").read_text(encoding="utf-8"))
    ok = (
        integrity.get("completeTraceCount") == integrity.get("executionCount")
        and integrity.get("incompleteTraceCount") == 0
        and integrity.get("sequenceGapCount") == 0
        and integrity.get("hashChainFailureCount") == 0
        and integrity.get("traceFooterMismatchCount") == 0
        and tamper.get("tamperCasesDetected") == 4
    )
    print("E_REVIEW_V24_AGENT_TRACE_INTEGRITY_PASS" if ok else "E_REVIEW_V24_AGENT_TRACE_INTEGRITY_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
