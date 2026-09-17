from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from scripts import run_step2123_reliability_analysis as baseline
from scripts import run_step213d_binary_router as binary
from scripts import run_step213e_setfit_binary_router as setfit


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "step213e_setfit_binary_router"


def read_json(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def read_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (OUTPUT / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def synthetic_case(**updates) -> dict:
    value = {
        "caseId": "setfit-test-case",
        "riskTypes": ["normal_review"],
        "severity": "low",
        "multiRisk": False,
        "ambiguity": False,
        "difficulty": "easy",
        "expressionType": "explicit",
        "boundaryType": None,
        "_partition": "TEST",
    }
    value.update(updates)
    return value


def candidate_metrics(**updates) -> dict:
    value = {
        "longRequiredRecall": 0.96,
        "highRiskFalseFastCount": 0,
        "materialSafetyFalseFastCount": 0,
        "fastPrecision": 0.96,
        "fastCoverage": 0.21,
    }
    value.update(updates)
    return value


def test_binary_target_unchanged():
    config = read_json("setfit_binary_training_config_v1.json")
    target_path = binary.DEFAULT_OUTPUT_DIR / "binary_router_target_definition_v1.json"
    assert config["binaryTargetDefinitionHash"] == baseline.sha256_file(target_path)
    assert binary.derive_binary_target(synthetic_case())["target"] == binary.FAST_ELIGIBLE
    assert binary.derive_binary_target(synthetic_case(severity="high"))["target"] == binary.LONG_REQUIRED


def test_same_fit_dev_split():
    split = setfit.load_fixed_split()
    training = read_json("setfit_binary_training_metrics_v1.json")
    assert split["counts"] == {"TRAIN": 64, "DEV": 16}
    assert training["internalSplitHash"] == split["splitHash"]
    assert training["trainTargetDistribution"] == {"FAST_ELIGIBLE": 36, "LONG_REQUIRED": 28}
    assert training["devTargetDistribution"] == {"FAST_ELIGIBLE": 9, "LONG_REQUIRED": 7}


def test_validation_not_training():
    config = read_json("setfit_binary_training_config_v1.json")
    training = read_json("setfit_binary_training_metrics_v1.json")
    assert config["validationUsedForTrainingOrTuning"] is False
    assert training["validationCasesSeen"] == 0


def test_boundary_not_training():
    config = read_json("setfit_binary_training_config_v1.json")
    training = read_json("setfit_binary_training_metrics_v1.json")
    assert config["boundaryUsedForTrainingOrTuning"] is False
    assert training["boundaryCasesSeen"] == 0


def test_frozen_not_executed():
    config = read_json("setfit_binary_training_config_v1.json")
    training = read_json("setfit_binary_training_metrics_v1.json")
    gate = read_json("step213e_setfit_gate_v1.json")
    assert config["frozenUsed"] is False
    assert training["frozenCasesSeen"] == 0
    assert gate["frozenBenchmarkExecuted"] is False
    assert gate["frozenGoldSha"] == baseline.FROZEN_GOLD_SHA


def test_single_base_encoder_only():
    snapshot = read_json("setfit_binary_model_snapshot_v1.json")
    config = read_json("setfit_binary_training_config_v1.json")
    assert snapshot["singleBaseEncoderOnly"] is True
    assert snapshot["generativeModel"] is False
    assert snapshot["modelId"] == config["baseEncoder"] == setfit.MODEL_ID
    assert snapshot["parameterCount"] == 23_953_920


def test_setfit_training_only_fit():
    config = read_json("setfit_binary_training_config_v1.json")
    training = read_json("setfit_binary_training_metrics_v1.json")
    assert config["trainingPartition"] == "FIT_INTERNAL_TRAIN_64_ONLY"
    assert training["trainingPartition"] == "FIT_INTERNAL_TRAIN_64_ONLY"
    assert training["trainingCaseCount"] == 64
    assert config["training"]["framework"] == "setfit"
    assert config["training"]["hyperparameterSearchCount"] == 0


def test_threshold_dev_only():
    threshold = read_json("setfit_binary_threshold_selection_v1.json")
    assert threshold["selectionPartition"] == "FIT_INTERNAL_DEV_16"
    assert threshold["candidateThresholds"] == [0.3, 0.4, 0.5, 0.6, 0.7]
    assert threshold["selectedThreshold"] in threshold["candidateThresholds"]
    assert threshold["validationUsed"] is False
    assert threshold["boundaryUsed"] is False
    assert threshold["frozenUsed"] is False


def test_safety_override():
    row = binary.make_output(
        synthetic_case(),
        score=0.01,
        threshold=0.7,
        rule_row={"safetyGateTriggered": True, "materialSafetyError": False},
        model_name="setfit_binary",
    )
    assert row["modelPrediction"] == binary.FAST_ELIGIBLE
    assert row["finalPrediction"] == binary.LONG_REQUIRED


def test_false_fast_metric():
    rows = read_jsonl("setfit_binary_validation_outputs_v1.jsonl")
    metric = read_json("setfit_binary_validation_metrics_v1.json")
    expected = sum(row["binaryTarget"] == binary.LONG_REQUIRED and row["finalPrediction"] == binary.FAST_ELIGIBLE for row in rows)
    assert metric["falseFastCount"] == expected
    assert metric["highRiskFalseFastCount"] == sum(row["highRiskFalseFast"] for row in rows)
    assert metric["materialSafetyFalseFastCount"] == sum(row["materialSafetyFalseFast"] for row in rows)


def test_fast_coverage_gate():
    assert setfit.candidate_gate(candidate_metrics()) == ("PASS", "BINARY_ROUTER_SHADOW_MODE")
    assert setfit.candidate_gate(candidate_metrics(longRequiredRecall=0.91, fastPrecision=0.91, fastCoverage=0.11)) == (
        "PASS_WITH_LIMITATIONS",
        "BINARY_ROUTER_SHADOW_MODE",
    )


def test_too_conservative_cannot_pass():
    status, recommendation = setfit.candidate_gate(candidate_metrics(fastCoverage=0.09))
    assert status == "FAIL_TOO_CONSERVATIVE"
    assert recommendation == "EXPAND_BINARY_TRAINING_POOL"


def test_safety_failure_cannot_pass():
    status, recommendation = setfit.candidate_gate(candidate_metrics(highRiskFalseFastCount=1))
    assert status == "FAIL_SAFETY"
    assert recommendation == "SETFIT_BINARY_ROUTER_UNSAFE"


def test_hard_negative_metrics():
    rows = [row for row in read_jsonl("setfit_binary_boundary_outputs_v1.jsonl") if row["boundaryType"] == "hard_negative"]
    metric = read_json("setfit_binary_boundary_metrics_v1.json")["hardNegative"]
    assert metric["caseCount"] == 15
    assert metric["fastTargetCount"] == 11
    captured = sum(row["binaryTarget"] == binary.FAST_ELIGIBLE and row["finalPrediction"] == binary.FAST_ELIGIBLE for row in rows)
    assert metric["falseEscalationCount"] + captured == metric["fastTargetCount"]
    assert 0 <= metric["fastRecall"] <= 1


def test_abstention_long():
    metric = read_json("setfit_binary_boundary_metrics_v1.json")["abstentionLongCapture"]
    assert metric == {"targetCount": 5, "captured": 5, "rate": 1.0}


def test_dataset_read_only():
    gate = read_json("step213e_setfit_gate_v1.json")
    assert gate["calibrationSha"] == baseline.CALIBRATION_SHA
    assert gate["boundarySha"] == baseline.BOUNDARY_SHA
    assert hashlib.sha256(baseline.DEFAULT_FROZEN.read_bytes()).hexdigest().upper() == baseline.FROZEN_GOLD_SHA
    assert gate["datasetModified"] is False


def test_no_qwen_call():
    gate = read_json("step213e_setfit_gate_v1.json")
    snapshot = read_json("setfit_binary_model_snapshot_v1.json")
    assert gate["qwenCallCount"] == 0
    assert "qwen" not in snapshot["modelId"].lower()


def test_no_external_api():
    gate = read_json("step213e_setfit_gate_v1.json")
    snapshot = read_json("setfit_binary_model_snapshot_v1.json")
    assert gate["externalApiCallCount"] == 0
    assert snapshot["externalApiCallCount"] == 0
    assert gate["longAnalysisExecuted"] is False
    assert gate["policyRagExecuted"] is False
    assert gate["reflectionExecuted"] is False


def test_three_way_comparison_uses_same_binary_cases():
    comparison = read_json("binary_router_three_way_comparison_v1.json")
    assert comparison["sameBinaryTarget"] is True
    assert comparison["sameValidationCases"] is True
    assert comparison["sameBoundaryCases"] is True
    assert set(comparison["validationSummary"]) == {"cheapRule", "frozenBgeLogistic", "setfitBinary"}
    assert comparison["oldTenLabelMetricsExcluded"] is True


def test_model_artifacts_match_snapshot():
    snapshot = read_json("setfit_binary_model_snapshot_v1.json")
    model_dir = OUTPUT / "setfit_binary_router_v1"
    assert baseline.sha256_file(model_dir / "model_head.pkl") == snapshot["classificationHeadSha"]
    assert (model_dir / "model.safetensors").is_file()
    assert (model_dir / "config_setfit.json").is_file()


def test_security_scan():
    paths = list(OUTPUT.rglob("*.json")) + list(OUTPUT.glob("*.jsonl")) + list(OUTPUT.rglob("*.md")) + [setfit.DEFAULT_REPORT]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert "chain-of-thought" not in payload.lower()
    assert "textZh" not in payload and "sanitizedText" not in payload
