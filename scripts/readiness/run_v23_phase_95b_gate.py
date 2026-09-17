from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-phase-95b-gate.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("decision") == "E_REVIEW_V23_PHASE_95B_PASS":
        print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_PASS")
        print("E_REVIEW_V23_PARENT_AWARE_FUSION_EVALUATION_PASS")
        print("E_REVIEW_V23_PHASE_95B_PASS")
        print("PHASE_95C_PARENT_CHILD_CHALLENGE_ALLOWED=true")
        return 0
    print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_BLOCKED")
    print("E_REVIEW_V23_PHASE_95B_BLOCKED")
    print("PHASE_95C_PARENT_CHILD_CHALLENGE_ALLOWED=false")
    for item in payload.get("blockingReasons", []):
        print(f"BLOCKED:{item}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
