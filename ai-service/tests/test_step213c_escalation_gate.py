from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path

from scripts import run_step2123_reliability_analysis as baseline
from scripts import run_step213c_escalation_gate as escalation


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "step213c_escalation"


def read_json(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def read_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (OUTPUT / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def signals(**updates) -> dict:
    value = {
        "intentType": "normal_feedback",
        "reasonCodes": ["NO_RISK_SIGNAL"],
        "requiresEvidence": False,
        "matchedRiskSignals": [],
        "routeCandidate": "low_touch",
        "rawConfidence": 0.88,
        "matchedRuleCount": 0,
        "safetyGateTriggered": False,
        "predictedRiskCount": 1,
        "predictedSeverity": "low",
    }
    value.update(updates)
    return value


def test_runtime_signals_only():
    inventory = read_json("escalation_signal_inventory_v1.json")
    used = {field for values in inventory["signalsUsedByCandidate"].values() for field in values}
    assert used <= set(escalation.RUNTIME_SIGNALS)


def test_no_gold_signal_in_score():
    inventory = read_json("escalation_signal_inventory_v1.json")
    assert inventory["goldOnlySignalUsedByScore"] == 0
    assert inventory["gate"] == "PASS"


def test_safety_override():
    score, route, triggered, overridden = escalation.route_signal("S0_MINIMAL", 4, signals(safetyGateTriggered=True))
    assert route == escalation.LONG_ANALYSIS
    assert overridden is True and "safety_override" in triggered
    assert score == 0


def test_threshold_candidates_fixed():
    artifact = read_json("escalation_score_candidates_v1.json")
    assert artifact["thresholdCandidates"] == [1, 2, 3, 4]
    assert {item["threshold"] for item in artifact["candidates"]} <= {1, 2, 3, 4}


def test_fit_only_policy_selection():
    policy = read_json("escalation_policy_v1.json")
    assert policy["selectionPartition"] == "CALIBRATION_FIT_80_ONLY"
    assert policy["fitOutputHash"]


def test_validation_not_used_for_threshold():
    policy = read_json("escalation_policy_v1.json")
    candidates = read_json("escalation_score_candidates_v1.json")
    assert policy["validationUsed"] is False
    assert candidates["validationUsed"] is False


def test_boundary_not_used_for_threshold():
    assert read_json("escalation_policy_v1.json")["boundaryUsed"] is False


def test_frozen_not_executed():
    gate = read_json("step213c_escalation_gate_v1.json")
    assert gate["frozenBenchmarkExecuted"] is False
    assert gate["frozenGoldSha"] == baseline.FROZEN_GOLD_SHA


def test_abstention_routes_long():
    rows = [row for row in read_jsonl("escalation_boundary_outputs_v1.jsonl") if row["evaluationTarget"] == "ABSTENTION"]
    gate = read_json("step213c_escalation_gate_v1.json")
    assert len(rows) == 5
    captured = sum(row["route"] == escalation.LONG_ANALYSIS for row in rows)
    assert gate["escalationAbstentionGate"] == ("PASS" if captured >= 4 else "FAIL")


def test_fast_path_safety():
    metric = read_json("escalation_validation_metrics_v1.json")["fastPath"]
    gate = read_json("step213c_escalation_gate_v1.json")
    expected = "PASS" if metric["materialSafetyErrorCount"] == 0 and read_json("escalation_validation_metrics_v1.json")["materialSafetyErrorCapture"]["rate"] >= 0.9 else "FAIL"
    assert gate["escalationSafetyGate"] == expected


def test_rule_error_capture():
    metric = read_json("escalation_validation_metrics_v1.json")["ruleErrorCapture"]
    assert 0 <= metric["captured"] <= metric["total"]
    assert 0 <= metric["rate"] <= 1


def test_false_escalation():
    metric = read_json("escalation_validation_metrics_v1.json")["falseEscalation"]
    assert metric["count"] <= metric["totalCorrectSafe"]
    assert 0 <= metric["rate"] <= 1


def test_long_analysis_rate():
    metric = read_json("escalation_validation_metrics_v1.json")
    assert metric["fastPath"]["count"] + metric["longAnalysis"]["count"] == metric["caseCount"]
    assert 0 <= metric["longAnalysis"]["rate"] <= 1


def test_policy_determinism():
    policy = read_json("escalation_policy_v1.json")
    spec = {key: value for key, value in policy.items() if key not in {"schemaVersion", "policyHash", "frozen"}}
    assert policy["policyHash"] == escalation.stable_hash(spec)
    rows = baseline.load_jsonl(escalation.RULE_RESULTS)
    fit = [row for row in rows if row["partition"] == "FIT"]
    _, rebuilt, _ = escalation.select_policy(fit)
    assert rebuilt["policyHash"] == policy["policyHash"]


def test_dataset_read_only():
    gate = read_json("step213c_escalation_gate_v1.json")
    assert gate["calibrationSha"] == baseline.CALIBRATION_SHA
    assert gate["boundarySha"] == baseline.BOUNDARY_SHA
    assert gate["frozenGoldSha"] == baseline.FROZEN_GOLD_SHA


def test_no_bge_call():
    source = inspect.getsource(escalation)
    assert "embedding_provider" not in source
    assert read_json("step213c_escalation_gate_v1.json")["bgeCallCount"] == 0


def test_no_qwen_call():
    source = inspect.getsource(escalation)
    assert "local_qwen" not in source
    assert read_json("step213c_escalation_gate_v1.json")["qwenCallCount"] == 0


def test_no_external_api():
    gate = read_json("step213c_escalation_gate_v1.json")
    assert gate["externalApiCallCount"] == 0
    assert gate["longAnalysisExecuted"] is False


def test_context_codes_not_invented():
    inventory = read_json("escalation_signal_inventory_v1.json")
    assert inventory["actualConflictUncertainAmbiguousCodes"] == []
    assert inventory["contextReasonScoreUsed"] is False


def test_raw_confidence_is_ordinal_auxiliary_only():
    inventory = read_json("escalation_signal_inventory_v1.json")
    assert inventory["rawConfidenceInterpretation"] == "LOW_CARDINALITY_ORDINAL_SIGNAL_NOT_PROBABILITY"
    assert "rawConfidence" not in inventory["signalsUsedByCandidate"]["S0_MINIMAL"]
    assert "rawConfidence" not in inventory["signalsUsedByCandidate"]["S1_RISK_AWARE"]
    assert "rawConfidence" in inventory["signalsUsedByCandidate"]["S2_ORDINAL_AUX"]


def test_score_formulas_are_bounded_integer_rules():
    for version in escalation.SCORE_VERSIONS:
        score, triggered = escalation.calculate_score(version, signals(requiresEvidence=True, matchedRiskSignals=["fake_review", "paid_review"], predictedRiskCount=2, predictedSeverity="high", rawConfidence=0.84))
        assert isinstance(score, int) and 0 <= score <= 6
        assert isinstance(triggered, list)


def test_output_is_explainable():
    row = read_jsonl("escalation_validation_outputs_v1.jsonl")[0]
    assert isinstance(row["escalationScore"], int)
    assert row["route"] in {escalation.FAST_PATH, escalation.LONG_ANALYSIS}
    assert isinstance(row["triggeredSignals"], list)
    assert isinstance(row["safetyOverride"], bool)


def test_security_scan():
    paths = list(OUTPUT.glob("*.json")) + list(OUTPUT.glob("*.jsonl")) + [escalation.DEFAULT_REPORT]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert "chain-of-thought" not in payload.lower()
    assert "sanitizedText" not in payload and "textZh" not in payload


def test_artifact_hashes_are_stable():
    policy = read_json("escalation_policy_v1.json")
    assert len(policy["policyHash"]) == 64
    assert hashlib.sha256(baseline.DEFAULT_FROZEN.read_bytes()).hexdigest().upper() == baseline.FROZEN_GOLD_SHA
