from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, AI_ROOT / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import pytest  # noqa: E402
from v23_parent_child_qc2_common import FORBIDDEN_SPLIT_ERROR, compare_runs, guard_calibration_split, run_frozen_calibration  # noqa: E402


def test_held_out_split_access_rejected() -> None:
    with pytest.raises(RuntimeError, match=FORBIDDEN_SPLIT_ERROR):
        guard_calibration_split("evaluation")
    with pytest.raises(RuntimeError, match=FORBIDDEN_SPLIT_ERROR):
        guard_calibration_split("challenge")


def test_frozen_calibration_repeat_hashes_match() -> None:
    first = run_frozen_calibration(split="calibration", run_id="pytest-1")
    second = run_frozen_calibration(split="calibration", run_id="pytest-2")
    comparison = compare_runs(first, second)
    assert comparison["metricsMatch"] is True
    assert comparison["allHashesMatch"] is True
    assert comparison["safetyPass"] is True
    assert first["configuration"]["parentRepresentation"] == "P2"
    assert first["configuration"]["parentTopN"] == 20
    assert first["configuration"]["postFusionCandidateK"] == 30
    assert first["configuration"]["allowBackfill"] is False
