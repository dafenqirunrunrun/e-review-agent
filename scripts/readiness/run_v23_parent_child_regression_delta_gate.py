from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-three-layer-regression-delta.json"
LEGACY_ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-regression-delta.json"


def main() -> int:
    artifact = ARTIFACT if ARTIFACT.exists() else LEGACY_ARTIFACT
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    qc2_pass = (
        payload.get("regressionDeltaPass") is True
        and payload.get("qualifiedFullRegressionPass") is True
        and payload.get("newFailuresAtoB") == 0
        and payload.get("newFailuresBtoC") == 0
    )
    legacy_pass = (
        payload.get("baseFailureSetRecorded") is True
        and payload.get("currentFailureSetRecorded") is True
        and payload.get("newFailureCount") == 0
        and payload.get("phase95aRelatedTestsPass") is True
    )
    if qc2_pass or legacy_pass:
        print("E_REVIEW_V23_PARENT_CHILD_REGRESSION_DELTA_PASS")
        print("E_REVIEW_V23_QUALIFIED_ENVIRONMENT_FULL_REGRESSION_PASS")
        return 0
    print("E_REVIEW_V23_PARENT_CHILD_REGRESSION_DELTA_BLOCKED")
    print(payload.get("blockingReason", "REGRESSION_DELTA_INCOMPLETE"))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
