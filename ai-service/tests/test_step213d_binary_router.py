from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path

import joblib

from scripts import run_step2123_reliability_analysis as baseline
from scripts import run_step213d_binary_router as binary


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "step213d_binary_router"


def read_json(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def read_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (OUTPUT / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def case(**updates) -> dict:
    value = {
        "caseId": "test-case",
        "riskTypes": ["normal_review"],
        "severity": "low",
        "multiRisk": False,
        "ambiguity": False,
        "difficulty": "easy",
        "expressionType": "explicit",
        "boundaryType": None,
    }
    value.update(updates)
    return value


def test_binary_target_derivation():
    assert binary.derive_binary_target(case())["target"] == binary.FAST_ELIGIBLE
    result = binary.derive_binary_target(case(riskTypes=["negative_review"], severity="medium"))
    assert result["target"] == binary.FAST_ELIGIBLE


def test_high_risk_always_long_target():
    result = binary.derive_binary_target(case(riskTypes=["normal_review"], severity="high"))
    assert result["target"] == binary.LONG_REQUIRED
    assert "HIGH_OR_CRITICAL_SEVERITY" in result["reasonCodes"]


def test_multirisk_long_target():
    result = binary.derive_binary_target(case(riskTypes=["normal_review", "negative_review"], severity="medium", multiRisk=True))
    assert result["target"] == binary.LONG_REQUIRED
    assert "MULTI_RISK" in result["reasonCodes"]


def test_abstention_long_target():
    result = binary.derive_binary_target(case(riskTypes=[], benchmarkRiskTypes=[], evaluationTarget="ABSTENTION"))
    assert result["target"] == binary.LONG_REQUIRED
    assert "ABSTENTION_TARGET" in result["reasonCodes"]


def test_after_sales_target_uses_governance_metadata_not_case_id():
    simple = case(riskTypes=["after_sales_risk"], severity="medium", difficulty="medium")
    complex_case = case(riskTypes=["after_sales_risk"], severity="medium", difficulty="hard", expressionType="implicit")
    hard_negative = case(riskTypes=["after_sales_risk"], severity="medium", difficulty="hard", expressionType="implicit", boundaryType="hard_negative")
    assert binary.derive_binary_target(simple)["target"] == binary.FAST_ELIGIBLE
    assert binary.derive_binary_target(complex_case)["target"] == binary.LONG_REQUIRED
    assert binary.derive_binary_target(hard_negative)["target"] == binary.FAST_ELIGIBLE
    assert "caseId" not in inspect.getsource(binary.is_complex_after_sales)


def test_fit_only_training():
    manifest = read_json("bge_binary_router_manifest_v1.json")
    assert manifest["trainingPartition"] == "CALIBRATION_FIT_80_ONLY"
    assert read_json("binary_router_internal_split_v1.json")["counts"] == {"TRAIN": 64, "DEV": 16}


def test_dev_only_threshold():
    threshold = read_json("binary_router_threshold_selection_v1.json")
    assert threshold["selectionPartition"] == "FIT_INTERNAL_DEV_16"
    assert threshold["trainingPartition"] == "FIT_INTERNAL_TRAIN_64"
    assert threshold["selectedThreshold"] in [0.3, 0.4, 0.5, 0.6, 0.7]


def test_validation_not_used_for_tuning():
    threshold = read_json("binary_router_threshold_selection_v1.json")
    manifest = read_json("bge_binary_router_manifest_v1.json")
    assert threshold["validationUsed"] is False
    assert manifest["validationUsedForTuning"] is False


def test_boundary_not_used_for_tuning():
    threshold = read_json("binary_router_threshold_selection_v1.json")
    manifest = read_json("bge_binary_router_manifest_v1.json")
    assert threshold["boundaryUsed"] is False
    assert manifest["boundaryUsedForTuning"] is False


def test_safety_override():
    row = binary.make_output(
        dict(case(), _partition="VALIDATION"),
        score=0.01,
        threshold=0.7,
        rule_row={"safetyGateTriggered": True, "materialSafetyError": False},
    )
    assert row["modelPrediction"] == binary.FAST_ELIGIBLE
    assert row["finalPrediction"] == binary.LONG_REQUIRED


def test_false_fast_metric():
    metric = read_json("binary_validation_metrics_v1.json")
    rows = read_jsonl("binary_validation_outputs_v1.jsonl")
    expected = sum(row["binaryTarget"] == binary.LONG_REQUIRED and row["finalPrediction"] == binary.FAST_ELIGIBLE for row in rows)
    assert metric["falseFastCount"] == expected
    assert 0 <= metric["falseFastRate"] <= 1


def test_high_risk_false_fast():
    metric = read_json("binary_validation_metrics_v1.json")
    rows = read_jsonl("binary_validation_outputs_v1.jsonl")
    assert metric["highRiskFalseFastCount"] == sum(row["highRiskFalseFast"] for row in rows)


def test_fast_precision():
    metric = read_json("binary_validation_metrics_v1.json")
    rows = [row for row in read_jsonl("binary_validation_outputs_v1.jsonl") if row["finalPrediction"] == binary.FAST_ELIGIBLE]
    expected = baseline.safe_ratio(sum(row["binaryTarget"] == binary.FAST_ELIGIBLE for row in rows), len(rows)) if rows else 0.0
    assert metric["fastPrecision"] == expected


def test_fast_coverage():
    metric = read_json("binary_validation_metrics_v1.json")
    assert sum(metric["predictionDistribution"].values()) == metric["caseCount"]
    assert metric["fastCoverage"] == baseline.safe_ratio(metric["predictionDistribution"][binary.FAST_ELIGIBLE], metric["caseCount"])


def test_abstention_long_capture():
    metric = read_json("binary_boundary_metrics_v1.json")["abstentionLongCapture"]
    assert metric["targetCount"] == 5
    assert 0 <= metric["captured"] <= 5


def test_hard_negative_metric():
    metric = read_json("binary_boundary_metrics_v1.json")["hardNegative"]
    assert metric["fastTargetCount"] > 0
    assert metric["fastCaptured"] + metric["falseEscalationCount"] == metric["fastTargetCount"]
    assert 0 <= metric["fastRecall"] <= 1


def test_frozen_not_executed():
    gate = read_json("step213d_binary_router_gate_v1.json")
    manifest = read_json("bge_binary_router_manifest_v1.json")
    assert gate["frozenBenchmarkExecuted"] is False
    assert manifest["frozenBenchmarkExecuted"] is False
    assert gate["frozenGoldSha"] == baseline.FROZEN_GOLD_SHA


def test_dataset_read_only():
    gate = read_json("step213d_binary_router_gate_v1.json")
    assert gate["calibrationSha"] == baseline.CALIBRATION_SHA
    assert gate["boundarySha"] == baseline.BOUNDARY_SHA
    assert hashlib.sha256(baseline.DEFAULT_FROZEN.read_bytes()).hexdigest().upper() == baseline.FROZEN_GOLD_SHA


def test_bge_frozen():
    manifest = read_json("bge_binary_router_manifest_v1.json")
    assert manifest["embeddingModelId"] == "BAAI/bge-m3"
    assert manifest["embeddingDimension"] == 1024
    assert manifest["encoderFrozen"] is True
    assert manifest["trainableEncoderParameterTensors"] == 0
    model_path = OUTPUT / "bge_binary_router_v1.joblib"
    assert hashlib.sha256(model_path.read_bytes()).hexdigest().upper() == manifest["modelArtifactSha"]
    artifact = joblib.load(model_path)
    assert artifact["positiveClass"] == binary.LONG_REQUIRED


def test_no_external_api():
    gate = read_json("step213d_binary_router_gate_v1.json")
    assert gate["externalApiCallCount"] == 0
    assert gate["qwenCallCount"] == 0
    assert gate["longAnalysisExecuted"] is False
    assert gate["policyRagExecuted"] is False
    assert gate["reflectionExecuted"] is False


def test_rule_and_bge_use_same_targets():
    comparison = read_json("rule_vs_binary_bge_v1.json")
    assert comparison["sameTargets"] is True
    assert comparison["sameEvaluationCases"] is True
    assert comparison["rulePolicy"]["scoreVersion"] == "S0_MINIMAL"


def test_target_audit_and_class_balance():
    audit = read_json("binary_target_audit_v1.json")
    assert audit["partitions"]["FIT"]["caseCount"] == 80
    assert audit["partitions"]["VALIDATION"]["caseCount"] == 40
    assert audit["partitions"]["BOUNDARY_CHALLENGE"]["caseCount"] == 60
    for partition in audit["partitions"].values():
        assert sum(partition["targets"].values()) == partition["caseCount"]


def test_security_scan():
    paths = list(OUTPUT.glob("*.json")) + list(OUTPUT.glob("*.jsonl")) + [binary.DEFAULT_REPORT]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert "chain-of-thought" not in payload.lower()
    assert "textZh" not in payload and "sanitizedText" not in payload
