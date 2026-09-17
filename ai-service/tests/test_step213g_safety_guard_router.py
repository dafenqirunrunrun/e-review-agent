from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path

from scripts import run_step2123_reliability_analysis as baseline
from scripts import run_step213g_safety_guard_router as guard


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "step213g_safety_guard_router"


def read_json(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def read_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (OUTPUT / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def runtime(**updates) -> dict:
    value = {
        "reviewText": "普通评价",
        "matchedRiskSignals": [],
        "reasonCodes": ["NO_RISK_SIGNAL"],
        "intentType": "normal_feedback",
        "safetyGateTriggered": False,
    }
    value.update(updates)
    return value


def business(**updates) -> dict:
    value = {
        "matchedBusinessRisks": [],
        "businessHighRiskTriggered": False,
        "abstentionSignal": False,
        "safetyGateTriggered": False,
    }
    value.update(updates)
    return value


def safety(unsafe: bool = False) -> dict:
    return {"unsafe": unsafe, "riskCategories": [], "score": 0.1, "model": guard.MODEL_ID}


def test_model_loading():
    manifest = read_json("safety_model_manifest_v1.json")
    gate = read_json("step213g_gate_v1.json")
    model_path = guard.DEFAULT_MODEL_DIR / "model.safetensors"
    assert manifest["model"] == guard.MODEL_ID
    assert manifest["parameterCount"] == 494_043_520
    assert baseline.sha256_file(model_path) == manifest["modelWeightsSha"]
    assert gate["safetyModelAvailabilityGate"] == gate["safetyModelRuntimeGate"] == "PASS"


def test_safety_output_schema():
    rows = read_jsonl("safety_model_predictions_v1.jsonl")
    assert len(rows) == 180
    for row in rows:
        decision = row["safetyDecision"]
        assert set(decision) == {"unsafe", "riskCategories", "score", "model"}
        assert isinstance(decision["unsafe"], bool)
        assert set(decision["riskCategories"]) <= set(guard.SAFETY_CATEGORIES)
        assert decision["model"] == guard.MODEL_ID


def test_no_model_training():
    manifest = read_json("safety_model_manifest_v1.json")
    gate = read_json("step213g_gate_v1.json")
    source = inspect.getsource(guard.load_model) + inspect.getsource(guard.run)
    assert manifest["trainingExecuted"] is False
    assert manifest["modelParametersModified"] is False
    assert gate["modelParametersModified"] is False
    assert ".backward(" not in source and "optimizer" not in source.lower()


def test_no_gold_signal_in_runtime():
    case = {
        "textZh": "测试文本",
        "riskTypes": ["fake_review"],
        "severity": "critical",
        "difficulty": "hard",
        "boundaryType": "test",
    }
    rule = {
        "matchedRiskSignals": [],
        "reasonCodes": [],
        "intentType": "normal_feedback",
        "safetyGateTriggered": False,
    }
    result = guard.runtime_input(case, rule)
    assert set(result) == set(guard.RUNTIME_INPUT_FIELDS)
    assert not set(result) & guard.PROHIBITED_RUNTIME_FIELDS
    policy = read_json("safety_router_policy_v1.json")
    assert not set(policy["runtimeInputFields"]) & set(policy["prohibitedRuntimeFields"])


def test_business_rule_isolated():
    assert "safety" not in inspect.signature(guard.business_rule_decision).parameters
    result = guard.business_rule_decision(runtime(reviewText="五星好评截图后返现，并要求删除差评"))
    assert result["businessHighRiskTriggered"] is True
    assert {"paid_review", "rating_manipulation", "review_suppression"} <= set(result["matchedBusinessRisks"])
    policy = read_json("safety_router_policy_v1.json")
    assert policy["businessRuleUsesSafetyModelOutput"] is False


def test_safety_override():
    assert guard.route_decision(safety(True), business())["safetyModelOnlyRoute"] == guard.LONG_ANALYSIS_CHAIN
    existing_gate = guard.route_decision(safety(), business(safetyGateTriggered=True))
    assert existing_gate["combinedRoute"] == guard.LONG_ANALYSIS_CHAIN
    assert "EXISTING_SAFETY_GATE" in existing_gate["combinedReasons"]


def test_abstention_long():
    result = guard.route_decision(safety(), business(abstentionSignal=True))
    assert result["combinedRoute"] == guard.LONG_ANALYSIS_CHAIN
    comparison = read_json("router_comparison_safety_guard_v1.json")
    assert comparison["safetyModelPlusBusinessRules"]["boundarySlices"]["abstention"] == {
        "targetCount": 5,
        "captured": 5,
        "rate": 1.0,
    }


def test_high_risk_false_fast():
    comparison = read_json("router_comparison_safety_guard_v1.json")
    validation = comparison["safetyModelPlusBusinessRules"]["validation"]
    boundary = comparison["safetyModelPlusBusinessRules"]["boundary"]
    assert validation["highRiskFalseFast"] == 7
    assert boundary["highRiskFalseFast"] == 33
    assert read_json("step213g_gate_v1.json")["safetyGuardRouterCandidateGate"] == "FAIL_SAFETY"


def test_boundary_evaluation():
    comparison = read_json("router_comparison_safety_guard_v1.json")
    candidate = comparison["safetyModelPlusBusinessRules"]
    assert set(candidate["boundarySlices"]) >= {
        "implicit_or_paraphrase",
        "multi_risk_or_conflict",
        "ambiguous_context",
        "hard_negative",
    }
    assert candidate["boundary"]["longRecall"] == 0.326531
    assert candidate["boundary"]["longAnalysisRate"] == 0.333333


def test_hard_negative_slice():
    hard = read_json("router_comparison_safety_guard_v1.json")["safetyModelPlusBusinessRules"]["boundarySlices"]["hardNegative"]
    assert hard["caseCount"] == 15
    assert hard["fastCoverage"] == 0.533333
    assert hard["falseEscalationCount"] == 4


def test_frozen_not_executed():
    gate = read_json("step213g_gate_v1.json")
    policy = read_json("safety_router_policy_v1.json")
    assert gate["frozenBenchmarkExecuted"] is False
    assert policy["frozenGoldUsed"] is False
    assert gate["frozenGoldSha"] == baseline.FROZEN_GOLD_SHA


def test_dataset_read_only():
    gate = read_json("step213g_gate_v1.json")
    assert gate["calibrationSha"] == baseline.CALIBRATION_SHA
    assert gate["boundarySha"] == baseline.BOUNDARY_SHA
    assert hashlib.sha256(baseline.DEFAULT_FROZEN.read_bytes()).hexdigest().upper() == baseline.FROZEN_GOLD_SHA
    assert gate["datasetReadOnlyGate"] == "PASS"


def test_stability():
    stability = read_json("router_comparison_safety_guard_v1.json")["stability"]
    assert stability == {"caseCount": 20, "consistentCount": 20, "decisionConsistency": 1.0}


def test_no_external_api():
    manifest = read_json("safety_model_manifest_v1.json")
    gate = read_json("step213g_gate_v1.json")
    assert manifest["externalInferenceApiCallCount"] == 0
    assert gate["externalApiCallCount"] == 0
    assert gate["longAnalysisExecuted"] is False
    assert gate["runtimeRouterModified"] is False


def test_security_scan():
    paths = list(OUTPUT.glob("*.json")) + list(OUTPUT.glob("*.jsonl")) + [guard.DEFAULT_REPORT]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert "textZh" not in payload and "sanitizedText" not in payload
