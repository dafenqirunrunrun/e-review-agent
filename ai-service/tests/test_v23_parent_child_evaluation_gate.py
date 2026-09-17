from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_phase_95b_gate_shape_if_present() -> None:
    artifact = ROOT / "artifacts" / "retrieval-optimization" / "v23-phase-95b-gate.json"
    if not artifact.exists():
        return
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["decision"] in {"E_REVIEW_V23_PHASE_95B_PASS", "E_REVIEW_V23_PHASE_95B_BLOCKED"}
    assert payload["challengeAccessed"] is False
    assert "phase95cParentChildChallengeAllowed" in payload
