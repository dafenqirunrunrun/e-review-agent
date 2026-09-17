from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-phase-95a-gate.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    required = [
        "sparseRouteClosurePass",
        "hierarchyPass",
        "parentIndexPass",
        "calibrationPass",
        "resourcePass",
        "defaultRegressionPass",
        "sensitiveScanPass",
    ]
    if all(payload.get(item) is True for item in required):
        print("E_REVIEW_V23_PHASE_95A_PASS")
        print("E_REVIEW_V23_PARENT_CHILD_RETRIEVAL_QUALIFIED")
        print("PHASE_95B_PARENT_CHILD_EVALUATION_ALLOWED=true")
        return 0
    print("E_REVIEW_V23_PHASE_95A_BLOCKED")
    print("PHASE_95B_PARENT_CHILD_EVALUATION_ALLOWED=false")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
