from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-evaluation-consumption-state.json"


def main() -> int:
    payload = json.loads(STATE.read_text(encoding="utf-8"))
    state = payload.get("state")
    if state in {"LOCKED", "CONSUMED_PASS", "CONSUMED_BLOCKED", "ABORTED_NO_RESULT"} and payload.get("challengeAccessed") is False:
        print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_CONSUMPTION_STATE_PASS")
        return 0
    print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_CONSUMPTION_STATE_BLOCKED")
    print(state)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
