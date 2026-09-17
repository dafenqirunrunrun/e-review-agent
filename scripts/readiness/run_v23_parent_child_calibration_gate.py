from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-calibration-decision.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("decision") == "VALID_PARENT_CHILD_CONFIGURATION" and payload.get("qualityPass") is True:
        print("E_REVIEW_V23_PARENT_CHILD_CALIBRATION_PASS")
        return 0
    print("E_REVIEW_V23_PARENT_CHILD_CALIBRATION_BLOCKED")
    for reason in payload.get("failureReasons", []):
        print(f"FAILED: {reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
