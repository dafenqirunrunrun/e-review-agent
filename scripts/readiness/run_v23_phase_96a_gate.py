from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-phase-96a-gate.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if p.get("decision") == "E_REVIEW_V23_PHASE_96A_PASS":
        print("E_REVIEW_V23_PHASE_96A_PASS")
        print("E_REVIEW_V23_RETRIEVAL_PROGRAM_CLOSED")
        print("E_REVIEW_V23_NO_NEW_RUNTIME_RETRIEVAL_CANDIDATE")
        print("V22_DETERMINISTIC_RETRIEVAL_REFERENCE_BASELINE_RETAINED")
        print("V24_AGENT_PRODUCTIONIZATION_ALLOWED=true")
        return 0
    print("E_REVIEW_V23_PHASE_96A_BLOCKED")
    print("V24_AGENT_PRODUCTIONIZATION_ALLOWED=false")
    for item in p.get("blockingReasons", []):
        print(f"BLOCKED:{item}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
