from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-phase-10b-gate.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if p.get("decision") == "E_REVIEW_V24_PHASE_10B_PASS":
        print("E_REVIEW_V24_PHASE_10B_PASS")
        print("E_REVIEW_V24_RUNTIME_TRACE_INTEGRATION_QUALIFIED")
        print("E_REVIEW_V24_CROSS_SERVICE_TRACE_PROPAGATION_QUALIFIED")
        print("E_REVIEW_V24_REAL_RETRIEVAL_TRACE_QUALIFIED")
        print("E_REVIEW_V24_REAL_LLM_TRACE_QUALIFIED")
        print("E_REVIEW_V24_RUNTIME_CONTEXT_ISOLATION_QUALIFIED")
        print("RUNTIME_TRACE_INTEGRATION_QUALIFIED_WHEN_EXPLICITLY_ENABLED")
        print("PHASE_10C_TRACE_STORAGE_QUERY_AND_OPERATIONS_ALLOWED=true")
        return 0
    print("E_REVIEW_V24_PHASE_10B_BLOCKED")
    for item in p.get("blockingReasons", []):
        print(f"BLOCKED:{item}")
    print("PHASE_10C_TRACE_STORAGE_QUERY_AND_OPERATIONS_ALLOWED=false")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
