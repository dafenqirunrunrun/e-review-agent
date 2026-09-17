from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path

import joblib
import numpy as np

from scripts import run_step213a2_discriminative_router as benchmark
from scripts import run_step213a_lite as qwen_base


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "step213a2_discriminative"


def read_json(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def test_bge_is_frozen():
    manifest = read_json("bge_m3_logistic_model_manifest_v1.json")
    assert manifest["encoderFrozen"] is True
    assert manifest["trainableEncoderParameterTensors"] == 0
    assert manifest["embeddingModelId"] == "BAAI/bge-m3"


def test_fit_only_training():
    manifest = read_json("bge_m3_logistic_model_manifest_v1.json")
    assert manifest["trainingPartition"] == "CALIBRATION_FIT_80_ONLY"
    assert manifest["thresholdSelectionPartition"] == "FIT_INTERNAL_TRAIN_64_DEV_16"


def test_validation_not_used_for_threshold():
    value = read_json("discriminative_threshold_selection_v1.json")
    assert value["validationUsed"] is False
    assert value["selectionPartition"] == "FIT_INTERNAL_DEV_16"


def test_boundary_not_used_for_threshold():
    value = read_json("discriminative_threshold_selection_v1.json")
    assert value["boundaryUsed"] is False


def test_frozen_not_executed():
    gate = read_json("step213a2_discriminative_gate_v1.json")
    assert gate["frozenBenchmarkExecuted"] is False
    assert gate["frozenGoldSha"] == qwen_base.FROZEN_GOLD_SHA


def test_multilabel_encoding():
    encoded = benchmark.multilabel_encode([{"riskTypes": ["after_sales_risk", "review_suppression"]}])
    assert encoded.shape == (1, 10)
    assert int(encoded.sum()) == 2
    assert encoded[0, benchmark.LABELS.index("after_sales_risk")] == 1
    assert encoded[0, benchmark.LABELS.index("review_suppression")] == 1


def test_rare_label_handling():
    vectors = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype="float32")
    targets = np.zeros((2, len(benchmark.LABELS)), dtype=np.int8)
    model, status = benchmark.fit_heads(vectors, targets)
    assert all(item["status"] == "UNTRAINABLE_LABEL" for item in status)
    assert np.all(benchmark.predict_scores(model, vectors) == 0)


def test_global_threshold_only():
    value = read_json("discriminative_threshold_selection_v1.json")
    assert value["strategy"] == "single-global-threshold"
    assert value["candidateThresholds"] == [0.3, 0.4, 0.5, 0.6]
    assert value["selectedGlobalThreshold"] in value["candidateThresholds"]


def test_normal_risk_exclusion():
    scores = np.zeros(len(benchmark.LABELS), dtype=float)
    scores[0] = 0.9
    scores[benchmark.LABELS.index("paid_review")] = 0.8
    decision, risks = benchmark.postprocess_scores(scores, 0.5)
    assert decision == "CLASSIFY"
    assert risks == ["paid_review"]


def test_abstention_rule():
    decision, risks = benchmark.postprocess_scores(np.full(len(benchmark.LABELS), 0.2), 0.5)
    assert decision == "ABSTAIN"
    assert risks == []


def test_material_safety_metric():
    row = benchmark.classification_row({"caseId": "x", "riskTypes": ["paid_review"], "textZh": "x", "_partition": "VALIDATION"}, np.asarray([0.9] + [0.0] * 9), 0.5)
    assert row["materialSafetyError"] is True
    assert row["highRiskAutoPassCandidate"] is True


def test_model_artifact_determinism():
    manifest = read_json("bge_m3_logistic_model_manifest_v1.json")
    model_path = OUTPUT / "bge_m3_logistic_router_v1.joblib"
    assert hashlib.sha256(model_path.read_bytes()).hexdigest().upper() == manifest["modelArtifactSha"]
    model = joblib.load(model_path)
    assert model["labels"] == list(benchmark.LABELS)
    assert model["globalThreshold"] == manifest["globalThreshold"]


def test_dataset_read_only():
    gate = read_json("step213a2_discriminative_gate_v1.json")
    assert gate["calibrationSha"] == qwen_base.CALIBRATION_SHA
    assert gate["boundarySha"] == qwen_base.BOUNDARY_SHA
    assert gate["frozenGoldSha"] == qwen_base.FROZEN_GOLD_SHA


def test_no_external_api():
    manifest = read_json("bge_m3_logistic_model_manifest_v1.json")
    gate = read_json("step213a2_discriminative_gate_v1.json")
    source = inspect.getsource(benchmark.run)
    assert manifest["externalApiCallCount"] == gate["externalApiCallCount"] == 0
    assert "HF_HUB_OFFLINE" in source and "TRANSFORMERS_OFFLINE" in source


def test_latency_measurement():
    quality = read_json("bge_logistic_quality_metrics_v1.json")
    latency = quality["latency"]
    assert latency["mode"] == "warm-single-request-batch-size-1"
    assert latency["caseCount"] == 100
    assert latency["embedding"]["p50Ms"] > 0
    assert latency["classifier"]["p50Ms"] > 0
    assert latency["endToEnd"]["p50Ms"] >= latency["embedding"]["p50Ms"]


def test_report_uses_quality_reliability_diagnostic():
    quality = read_json("bge_logistic_quality_metrics_v1.json")
    report = benchmark.build_report(
        read_json("bge_m3_logistic_model_manifest_v1.json"),
        read_json("discriminative_label_support_v1.json"),
        read_json("discriminative_threshold_selection_v1.json"),
        quality,
        read_json("rule_vs_bge_logistic_comparison_v1.json"),
        read_json("diagnostic_20case_three_way_comparison_v1.json"),
        quality["latency"],
        read_json("step213a2_discriminative_gate_v1.json"),
    )
    assert "GE_0_8" in report


def test_embedding_cache_rerun_preserves_initial_extraction_time():
    manifest = read_json("bge_m3_embedding_cache_manifest_v1.json")
    if manifest["cacheHitCount"] == manifest["caseCount"]:
        assert manifest["embeddingExtractionTimeMs"] > 0
        assert manifest["currentRunCacheLookupTimeMs"] >= 0


def test_security_scan():
    paths = list(OUTPUT.glob("*.json")) + list(OUTPUT.glob("*.jsonl")) + [benchmark.DEFAULT_REPORT]
    payload = "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())
    assert not re.search(r"[A-Za-z]:\\", payload)
    assert not re.search(r"authorization\s*[=:]", payload, re.I)
    assert not re.search(r"api[_-]?key\s*[=:]", payload, re.I)
    assert "chain-of-thought" not in payload.lower()
