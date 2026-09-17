from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-evaluation-lock.json"


EXPECTED = {
    "parentRepresentation": "P2",
    "strategy": "H2",
    "configuredParentTopN": 20,
    "parentPriorEnabled": True,
    "parentPriorConstant": 60,
    "postFusionCandidateK": 30,
    "maximumFinalK": 5,
    "allowBackfill": False,
}


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    drift = [key for key, value in EXPECTED.items() if payload.get(key) != value]
    if not drift and payload.get("effectiveParentTopN") == 18 and payload.get("hierarchicalScopeReduction") is False:
        print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_LOCK_PASS")
        return 0
    print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_LOCK_BLOCKED")
    for item in drift:
        print(f"DRIFT:{item}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
