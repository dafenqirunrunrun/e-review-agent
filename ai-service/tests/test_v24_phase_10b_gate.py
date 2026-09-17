from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_phase_10b_gate_blocks_when_real_assets_are_unavailable() -> None:
    payload = json.loads((ROOT / "artifacts" / "agent-productionization" / "v24-phase-10b-gate.json").read_text(encoding="utf-8"))
    if payload["blockingReasons"]:
        assert payload["decision"] == "E_REVIEW_V24_PHASE_10B_BLOCKED"
        assert payload["phase10cTraceStorageQueryAndOperationsAllowed"] is False
    assert payload["productionTraceEnabled"] is False
    assert payload["productionReplayEnabled"] is False
    assert payload["challengeAccessed"] is False
