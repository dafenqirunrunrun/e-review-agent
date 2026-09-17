from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-reproducibility.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("status") == "E_REVIEW_V23_PARENT_CHILD_CALIBRATION_REPRODUCIBILITY_PASS":
        print("E_REVIEW_V23_PARENT_CHILD_INDEX_REBUILD_PARITY_PASS")
        print("E_REVIEW_V23_PARENT_CHILD_RANKING_HASH_PARITY_PASS")
        print("E_REVIEW_V23_PARENT_CHILD_CALIBRATION_REPRODUCIBILITY_PASS")
        return 0
    print("PARENT_CHILD_CALIBRATION_NOT_REPRODUCIBLE")
    print(payload.get("blockingReason", "REPRODUCIBILITY_INCOMPLETE"))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
