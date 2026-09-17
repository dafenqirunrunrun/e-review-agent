from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

from scripts import run_step213a_lite as qwen_base
from scripts import run_step213b_hybrid_router as hybrid


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "step213b_hybrid"


def read_json(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def read_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (OUTPUT / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def rule_signal(risks: list[str], *, safety: bool = False, route: str = "governance_required", intent: str = "risk_review") -> dict:
    return {
        "predictedRiskTypes": risks,
        "intentType": intent,
        "reasonCodes": ["HIGH_RISK_SAFETY_GATE"] if safety else ["TEST_KEYWORD"],
        "requiresEvidence": bool(set(risks) - {"normal_review"}),
        "matchedRiskSignals": list(set(risks) - {"normal_review"}),
        "matchedRuleCount": 1,
        "safetyGateTriggered": safety,
        "predictedSeverity": "high" if safety else "medium",
        "routeCandidate": route,
    }


def bge_signal(risks: list[str], scores: dict[str, float] | None = None, *, decision: str = "CLASSIFY") -> dict:
    values = {label: 0.1 for label in hybrid.discriminative.LABELS}
    for risk in risks:
        values[risk] = 0.8
    values.update(scores or {})
    ordered = sorted(values.values(), reverse=True)
    return {
        "predictedRiskTypes": risks,
        "classificationScores": values,
        "scoreSignals": {"maxScore": ordered[0], "secondScore": ordered[1], "top1Top2Margin": ordered[0] - ordered[1], "predictedLabelCount": len(risks)},
        "decision": decision,
    }


def test_oof_no_training_leakage():
    split = read_json("hybrid_oof_split_v1.json")
    tests = []
    for fold in split["folds"]:
        assert not set(fold["trainCaseIds"]) & set(fold["testCaseIds"])
        assert fold["trainCount"] == 64 and fold["testCount"] == 16
        tests.extend(fold["testCaseIds"])
    assert len(tests) == len(set(tests)) == 80


def test_fit_only_policy_selection():
    selected = read_json("hybrid_policy_selected_v1.json")
    assert selected["selectionPartition"] == "CALIBRATION_FIT_80_OOF_ONLY"
    assert selected["fitOofHash"]


def test_validation_not_used_for_policy():
    assert read_json("hybrid_policy_selected_v1.json")["validationUsed"] is False
    assert read_json("hybrid_policy_candidates_v1.json")["validationUsed"] is False


def test_boundary_not_used_for_policy():
    assert read_json("hybrid_policy_selected_v1.json")["boundaryUsed"] is False


def test_frozen_not_executed():
    gate = read_json("step213b_hybrid_gate_v1.json")
    assert gate["frozenBenchmarkExecuted"] is False
    assert gate["frozenGoldSha"] == qwen_base.FROZEN_GOLD_SHA


def test_gold_signal_not_used():
    audit = read_json("hybrid_signal_leakage_audit_v1.json")
    assert audit["goldOnlySignalUsedByPolicy"] == 0
    assert audit["gate"] == "PASS"


def test_rule_output_not_overwritten():
    base = {
        "ruleSignals": rule_signal(["paid_review"]),
        "bgeSignals": bge_signal(["fake_review", "paid_review"]),
        "finalRiskTypes": ["paid_review"],
    }
    row = hybrid.simulate([base], "H2_SEMANTIC_GUARD", 0.5)[0]
    assert row["route"] == hybrid.STRICT_PATH
    assert row["finalRiskTypes"] == ["paid_review"]


def test_bge_only_guard_not_primary():
    for row in read_jsonl("hybrid_validation_outputs_v1.jsonl"):
        assert row["finalRiskTypes"] == row["ruleSignals"]["predictedRiskTypes"]


def test_h1_consensus():
    agree = {"rule": rule_signal(["paid_review"]), "bge": bge_signal(["paid_review"])}
    disagree = {"rule": rule_signal(["paid_review"]), "bge": bge_signal(["fake_review"])}
    assert hybrid.h1_consensus(agree)[0] == hybrid.FAST_PATH
    assert hybrid.h1_consensus(disagree)[0] == hybrid.STRICT_PATH


def test_h2_semantic_guard():
    signals = {"rule": rule_signal(["normal_review"]), "bge": bge_signal(["paid_review"])}
    route, reasons = hybrid.h2_semantic_guard(signals, 0.5)
    assert route == hybrid.STRICT_PATH
    assert "RULE_NORMAL_BGE_RISK" in reasons


def test_h3_risk_presence():
    agreement = {"rule": rule_signal(["paid_review"]), "bge": bge_signal(["fake_review"])}
    conflict = {"rule": rule_signal(["normal_review"]), "bge": bge_signal(["fake_review"])}
    assert hybrid.h3_risk_presence(agreement)[0] == hybrid.FAST_PATH
    assert hybrid.h3_risk_presence(conflict)[0] == hybrid.STRICT_PATH


def test_guard_threshold_candidates_fixed():
    candidates = read_json("hybrid_policy_candidates_v1.json")
    assert candidates["guardThresholdCandidates"] == [0.3, 0.5, 0.7]


def test_policy_freeze():
    selected = read_json("hybrid_policy_selected_v1.json")
    assert selected["frozen"] is True
    assert selected["policyName"] in hybrid.POLICY_NAMES
    assert selected["policyHash"]


def test_rule_error_capture():
    metric = read_json("hybrid_validation_metrics_v1.json")["ruleErrorCapture"]
    assert 0 <= metric["captured"] <= metric["total"]
    assert 0 <= metric["rate"] <= 1


def test_multi_risk_capture():
    metric = read_json("hybrid_validation_metrics_v1.json")["multiRiskMissCapture"]
    assert 0 <= metric["captured"] <= metric["total"]


def test_material_safety_capture():
    metric = read_json("hybrid_validation_metrics_v1.json")["materialSafetyErrorCapture"]
    assert 0 <= metric["rate"] <= 1


def test_false_escalation():
    metric = read_json("hybrid_validation_metrics_v1.json")["falseEscalation"]
    assert metric["count"] <= metric["totalRuleCorrect"]
    assert 0 <= metric["rate"] <= 1


def test_selective_accuracy():
    metric = read_json("hybrid_validation_metrics_v1.json")["fastPath"]
    assert 0 <= metric["exactAccuracy"] <= 1
    assert 0 <= metric["coverage"] <= 1


def test_abstention_not_fast_path():
    rows = [row for row in read_jsonl("hybrid_boundary_outputs_v1.jsonl") if row["evaluationTarget"] == "ABSTENTION"]
    assert len(rows) == 5
    assert sum(row["route"] != hybrid.FAST_PATH for row in rows) >= 4


def test_hard_negative_metrics():
    metric = read_json("hybrid_boundary_metrics_v1.json")["hardNegative"]
    assert metric["caseCount"] == 15
    assert metric["fastPathAccuracy"] is None or 0 <= metric["fastPathAccuracy"] <= 1
    assert 0 <= metric["escalationRate"] <= 1


def test_candidate_gate_uses_boundary_abstention_cases():
    metric = read_json("hybrid_boundary_metrics_v1.json")["abstentionStrictCapture"]
    gate = read_json("step213b_hybrid_gate_v1.json")
    assert metric["targetCount"] == 5
    assert gate["hybridAbstentionGate"] == ("PASS" if metric["captured"] >= 4 else "FAIL")


def test_latency():
    metric = read_json("hybrid_latency_metrics_v1.json")
    assert metric["mode"] == "warm-single-request-batch-size-1"
    assert metric["caseCount"] == 100
    assert metric["p50Ms"] > 0 and metric["p95Ms"] >= metric["p50Ms"]


def test_dataset_read_only():
    gate = read_json("step213b_hybrid_gate_v1.json")
    assert gate["calibrationSha"] == qwen_base.CALIBRATION_SHA
    assert gate["boundarySha"] == qwen_base.BOUNDARY_SHA
    assert gate["frozenGoldSha"] == qwen_base.FROZEN_GOLD_SHA


def test_no_external_api():
    gate = read_json("step213b_hybrid_gate_v1.json")
    source = inspect.getsource(hybrid.run)
    assert gate["externalApiCallCount"] == 0
    assert "HF_HUB_OFFLINE" in source and "TRANSFORMERS_OFFLINE" in source
    assert "qwen" not in inspect.getsource(hybrid.latency_metrics).lower()


def test_security_scan():
    paths = list(OUTPUT.glob("*.json")) + list(OUTPUT.glob("*.jsonl")) + [hybrid.DEFAULT_REPORT]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert "chain-of-thought" not in payload.lower()
    assert "sanitizedText" not in payload and "textZh" not in payload
