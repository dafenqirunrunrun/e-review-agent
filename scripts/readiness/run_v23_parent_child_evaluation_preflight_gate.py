from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-evaluation-preflight.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = (
        payload.get("preflightPass") is True
        and payload.get("fallbackUsed") is False
        and payload.get("heldoutEvaluationReadCount") == 0
        and payload.get("challengeReadCount") == 0
    )
    if ok:
        print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_PREFLIGHT_PASS")
        return 0
    print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_PREFLIGHT_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
