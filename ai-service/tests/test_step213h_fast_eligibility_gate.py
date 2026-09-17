from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from scripts import run_step2123_reliability_analysis as baseline
from scripts import run_step213h_fast_eligibility_gate as fast_gate


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "step213h_fast_eligibility_gate"


def read_json(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def read_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (OUTPUT / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def runtime(**updates) -> dict:
    value = {
        "reviewText": "商品很好，物流很快，下次还会购买。",
        "intentType": "normal_feedback",
        "matchedRiskSignals": [],
        "reasonCodes": ["NO_RISK_SIGNAL"],
        "routeCandidate": "low_touch",
        "safetyGateTriggered": False,
    }
    value.update(updates)
    return value


def metrics(**updates) -> dict:
    value = {
        "longRequiredRecall": 1.0,
        "fastPrecision": 1.0,
        "fastCoverage": 0.25,
        "highRiskFalseFastCount": 0,
        "materialSafetyFalseFastCount": 0,
    }
    value.update(updates)
    return value


def test_policy_is_default_long_allowlist():
    policy = read_json("fast_eligibility_policy_v1.json")
    assert policy["defaultRoute"] == fast_gate.LONG_ANALYSIS_CHAIN
    assert policy["fastEligibilityRules"] == ["STANDARD_LOW_COMPLEXITY_ISSUE", "CLEAR_ORDINARY_REVIEW"]
    assert policy["modelUsed"] is False
    assert policy["frozen"] is True


def test_clear_ordinary_review_is_fast():
    result = fast_gate.route(runtime())
    assert result == {"route": fast_gate.FAST_SHORT_CHAIN, "reasonCode": "CLEAR_ORDINARY_REVIEW", "eligible": True}


def test_standard_issue_is_fast():
    result = fast_gate.route(
        runtime(
            reviewText="收到后发现尺寸偏大，不太合适。",
            intentType="normal_feedback",
        )
    )
    assert result["route"] == fast_gate.FAST_SHORT_CHAIN
    assert result["reasonCode"] == "STANDARD_LOW_COMPLEXITY_ISSUE"


def test_existing_safety_gate_is_long():
    result = fast_gate.route(runtime(safetyGateTriggered=True))
    assert result["route"] == fast_gate.LONG_ANALYSIS_CHAIN
    assert result["reasonCode"] == "EXISTING_SAFETY_GATE"


def test_business_governance_signal_is_long():
    result = fast_gate.route(runtime(matchedRiskSignals=["fake_review"], routeCandidate="governance_required"))
    assert result["route"] == fast_gate.LONG_ANALYSIS_CHAIN
    assert result["reasonCode"] == "GOVERNANCE_RISK_SIGNAL"


def test_reward_or_review_condition_is_long():
    result = fast_gate.route(runtime(reviewText="五星好评截图后返现，必须先修改评价。"))
    assert result["route"] == fast_gate.LONG_ANALYSIS_CHAIN
    assert result["reasonCode"] == "HARD_LONG_TEXT_SIGNAL"


def test_uncertain_context_is_long():
    result = fast_gate.route(runtime(reviewText="客服说处理后再联系，但不清楚是否需要修改公开内容。"))
    assert result["route"] == fast_gate.LONG_ANALYSIS_CHAIN
    assert result["reasonCode"] == "HARD_LONG_TEXT_SIGNAL"


def test_unproven_case_defaults_long():
    result = fast_gate.route(runtime(reviewText="今天收到商品。", intentType="normal_feedback"))
    assert result == {"route": fast_gate.LONG_ANALYSIS_CHAIN, "reasonCode": "FAST_ELIGIBILITY_NOT_PROVEN", "eligible": False}


def test_runtime_input_excludes_gold_and_source():
    case = {
        "textZh": "普通评论",
        "riskTypes": ["fake_review"],
        "severity": "critical",
        "boundaryType": "test",
        "sourceDataset": "hidden-source",
    }
    rule = {
        "intentType": "normal_feedback",
        "matchedRiskSignals": [],
        "reasonCodes": [],
        "routeCandidate": "low_touch",
        "safetyGateTriggered": False,
    }
    result = fast_gate.runtime_input(case, rule)
    assert set(result) == set(fast_gate.RUNTIME_INPUT_FIELDS)
    assert not set(result) & fast_gate.PROHIBITED_RUNTIME_FIELDS


def test_fit_dev_policy_frozen_before_validation():
    freeze = read_json("fit_dev_policy_freeze_v1.json")
    policy = read_json("fast_eligibility_policy_v1.json")
    assert freeze["selectionPartition"] == "FIT_INTERNAL_TRAIN_64_AND_DEV_16"
    assert freeze["validationUsed"] is False
    assert freeze["boundaryUsed"] is False
    assert freeze["policyHash"] == policy["policyHash"]
    assert freeze["trainMetrics"]["highRiskFalseFast"] == 0
    assert freeze["devMetrics"]["highRiskFalseFast"] == 0


def test_validation_metrics_meet_candidate_gate():
    validation = read_json("fast_eligibility_validation_metrics_v1.json")
    boundary = read_json("fast_eligibility_boundary_metrics_v1.json")
    assert validation["longRequiredRecall"] == 1.0
    assert validation["fastPrecision"] == 1.0
    assert validation["fastCoverage"] == 0.275
    assert validation["highRiskFalseFastCount"] == 0
    assert validation["materialSafetyFalseFastCount"] == 0
    assert fast_gate.candidate_gate(validation, boundary) == ("PASS", "FAST_ELIGIBILITY_SHADOW_MODE")


def test_all_long_cannot_pass():
    status, recommendation = fast_gate.candidate_gate(metrics(fastCoverage=0.0), metrics())
    assert status == "FAIL_TOO_CONSERVATIVE"
    assert recommendation == "FAST_ELIGIBILITY_COVERAGE_INSUFFICIENT"


def test_safety_failure_cannot_pass():
    status, _ = fast_gate.candidate_gate(metrics(highRiskFalseFastCount=1), metrics())
    assert status == "FAIL_SAFETY"
    status, _ = fast_gate.candidate_gate(metrics(), metrics(materialSafetyFalseFastCount=1))
    assert status == "FAIL_SAFETY"


def test_boundary_and_abstention():
    boundary = read_json("fast_eligibility_boundary_metrics_v1.json")
    assert boundary["caseCount"] == 60
    assert boundary["longRequiredRecall"] == 1.0
    assert boundary["highRiskFalseFastCount"] == 0
    assert boundary["materialSafetyFalseFastCount"] == 0
    assert boundary["abstentionLongCapture"] == {"targetCount": 5, "captured": 5, "rate": 1.0}


def test_hard_negative_is_reported_not_hidden():
    hard = read_json("fast_eligibility_boundary_metrics_v1.json")["hardNegative"]
    assert hard["caseCount"] == 15
    assert hard["fastTargetCount"] == 11
    assert hard["fastRecall"] == 0.0
    assert hard["falseEscalationCount"] == 11


def test_deterministic_reasoned_outputs():
    gate = read_json("step213h_gate_v1.json")
    rows = read_jsonl("fast_eligibility_validation_outputs_v1.jsonl")
    assert gate["stability"] == {"caseCount": 20, "consistentCount": 20, "decisionConsistency": 1.0}
    assert len(rows) == 40
    assert all(row["reasonCode"] and row["route"] in {fast_gate.FAST_SHORT_CHAIN, fast_gate.LONG_ANALYSIS_CHAIN} for row in rows)


def test_no_model_external_or_frozen_execution():
    gate = read_json("step213h_gate_v1.json")
    assert gate["modelUsed"] is False
    assert gate["modelTrainingExecuted"] is False
    assert gate["externalApiCallCount"] == 0
    assert gate["frozenBenchmarkExecuted"] is False
    assert gate["longAnalysisExecuted"] is False
    assert gate["runtimeRouterModified"] is False


def test_dataset_read_only():
    gate = read_json("step213h_gate_v1.json")
    assert gate["calibrationSha"] == baseline.CALIBRATION_SHA
    assert gate["boundarySha"] == baseline.BOUNDARY_SHA
    assert hashlib.sha256(baseline.DEFAULT_FROZEN.read_bytes()).hexdigest().upper() == baseline.FROZEN_GOLD_SHA
    assert gate["datasetReadOnlyGate"] == "PASS"


def test_security_scan():
    paths = list(OUTPUT.glob("*.json")) + list(OUTPUT.glob("*.jsonl")) + [fast_gate.DEFAULT_REPORT]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert "textZh" not in payload and "sanitizedText" not in payload
