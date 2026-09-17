from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def test_challenge_preserved_if_present() -> None:
    path = OUT / "v23-retrieval-challenge-preservation.json"
    if not path.exists():
        return
    p = json.loads(path.read_text(encoding="utf-8"))
    assert p["challengeCaseCount"] == 75
    assert p["challengeQueryHashesRead"] is False
    assert p["challengeLabelsRead"] is False
    assert p["challengeRetrievalExecuted"] is False
    assert p["challengeMetricsGenerated"] is False


def test_program_closure_final_decision_if_present() -> None:
    path = OUT / "v23-retrieval-program-closure.json"
    if not path.exists():
        return
    p = json.loads(path.read_text(encoding="utf-8"))
    assert p["programClosed"] is True
    assert p["qualifiedNewRuntimeCandidateCount"] == 0
    assert p["runtimePromotion"] is False
    assert p["referenceBaselineRetained"] is True
    assert p["v24AgentProductionizationAllowed"] is True


def test_phase_96a_gate_if_present() -> None:
    path = OUT / "v23-phase-96a-gate.json"
    if not path.exists():
        return
    p = json.loads(path.read_text(encoding="utf-8"))
    assert p["decision"] == "E_REVIEW_V23_PHASE_96A_PASS"
    assert p["v23NewRetrievalRuntimeCandidate"] == "NONE"
    assert p["v23RuntimePromotionAllowed"] is False
    assert p["v22DeterministicRetrievalReferenceBaselineRetained"] is True
