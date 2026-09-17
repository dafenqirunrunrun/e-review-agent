from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, AI_ROOT / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from v23_parent_child_heldout_common import validate_transition  # noqa: E402


def test_consumption_state_legal_transitions() -> None:
    assert validate_transition("UNCONSUMED", "LOCKED", result_generated=False)
    assert validate_transition("LOCKED", "RUNNING", result_generated=False)
    assert validate_transition("RUNNING", "CONSUMED_PASS", result_generated=True)
    assert validate_transition("RUNNING", "CONSUMED_BLOCKED", result_generated=True)
    assert validate_transition("RUNNING", "ABORTED_NO_RESULT", result_generated=False)


def test_consumption_state_rejects_rerun_and_bad_abort() -> None:
    assert not validate_transition("CONSUMED_PASS", "RUNNING", result_generated=True)
    assert not validate_transition("CONSUMED_BLOCKED", "RUNNING", result_generated=True)
    assert not validate_transition("RUNNING", "ABORTED_NO_RESULT", result_generated=True)
