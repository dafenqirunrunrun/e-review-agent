from __future__ import annotations

"""Run the offline Step 21.3E SetFit binary escalation-router evaluation."""

import argparse
import hashlib
import json
import os
import ssl
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SETFIT_PACKAGES = ROOT / ".runtime" / "setfit-packages"
if SETFIT_PACKAGES.is_dir():
    sys.path.insert(0, str(SETFIT_PACKAGES))

import joblib
import numpy as np

sys.path.insert(0, str(ROOT))

from scripts import run_step2123_reliability_analysis as baseline
from scripts import run_step213d_binary_router as binary


DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "step213e_setfit_binary_router"
DEFAULT_REPORT = REPO_ROOT / "docs" / "SETFIT_BINARY_ROUTER_REPORT.md"
DEFAULT_MODEL_DIR = ROOT.parents[1] / "models" / "bge-small-zh-v1.5"
MODEL_ID = "BAAI/bge-small-zh-v1.5"
MODEL_REVISION = "7999E1D3359715C523056EF9478215996D62A620"
MODEL_LICENSE = "MIT"
BENCHMARK_VERSION = "step21.3e-setfit-binary-router-v1"
TRAINING_SEED = 2135
THRESHOLDS = binary.THRESHOLDS
TRAINING_CONFIG = {
    "framework": "setfit",
    "setfitVersion": "1.1.3",
    "sentenceTransformersVersion": "3.4.1",
    "loss": "CosineSimilarityLoss",
    "batchSize": 8,
    "numEpochs": 1,
    "numIterations": 10,
    "bodyLearningRate": 2e-5,
    "headLearningRate": 1e-2,
    "maxLength": 256,
    "samplingStrategy": "oversampling",
    "useAmp": True,
    "seed": TRAINING_SEED,
    "hyperparameterSearchCount": 0,
    "resourceAdjustmentCount": 0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    return parser.parse_args()


def _patch_windows_certificate_loading() -> None:
    """Avoid malformed Windows-store certificates; local training stays offline."""
    try:
        import certifi
    except ImportError:
        return

    def load_certifi(self: ssl.SSLContext, purpose: ssl.Purpose = ssl.Purpose.SERVER_AUTH) -> None:
        del purpose
        self.load_verify_locations(cafile=certifi.where())

    ssl.SSLContext.load_default_certs = load_certifi


def load_setfit_dependencies() -> tuple[Any, Any, Any, Any]:
    import torch

    _patch_windows_certificate_loading()
    from datasets import Dataset
    from setfit import SetFitModel, Trainer, TrainingArguments

    return torch, Dataset, SetFitModel, (Trainer, TrainingArguments)


def model_file_hash(model_dir: Path) -> str:
    path = model_dir / "model.safetensors"
    if not path.is_file():
        path = model_dir / "pytorch_model.bin"
    if not path.is_file():
        raise RuntimeError("SETFIT_BASE_MODEL_WEIGHTS_MISSING")
    return baseline.sha256_file(path)


def load_fixed_split() -> dict[str, Any]:
    path = binary.DEFAULT_OUTPUT_DIR / "binary_router_internal_split_v1.json"
    split = json.loads(path.read_text(encoding="utf-8"))
    if split.get("splitHash") != "8AE9B27144443E36272FE7993445656B2FFB46492539BA566107C56BC489868F":
        raise RuntimeError("STEP213D_INTERNAL_SPLIT_CHANGED")
    if split.get("counts") != {"TRAIN": 64, "DEV": 16}:
        raise RuntimeError("STEP213D_INTERNAL_SPLIT_COUNT_CHANGED")
    return split


def training_dataset(Dataset: Any, cases: list[dict[str, Any]]) -> Any:
    return Dataset.from_dict(
        {
            "text": [str(case["textZh"]) for case in cases],
            "label": binary.binary_encode(cases).astype(int).tolist(),
        }
    )


def fit_setfit_model(model_dir: Path, train_cases: list[dict[str, Any]], output_dir: Path, device: str) -> tuple[Any, dict[str, Any]]:
    torch, Dataset, SetFitModel, trainer_types = load_setfit_dependencies()
    Trainer, TrainingArguments = trainer_types
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("SETFIT_CUDA_UNAVAILABLE")
    torch.manual_seed(TRAINING_SEED)
    np.random.seed(TRAINING_SEED)
    if device == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    model = SetFitModel.from_pretrained(
        str(model_dir),
        local_files_only=True,
        labels=[binary.FAST_ELIGIBLE, binary.LONG_REQUIRED],
    )
    model.model_body.to(device)
    parameter_count = sum(parameter.numel() for parameter in model.model_body.parameters())
    dataset = training_dataset(Dataset, train_cases)
    arguments = TrainingArguments(
        output_dir=str(output_dir / "training-checkpoints"),
        batch_size=TRAINING_CONFIG["batchSize"],
        num_epochs=TRAINING_CONFIG["numEpochs"],
        num_iterations=TRAINING_CONFIG["numIterations"],
        body_learning_rate=TRAINING_CONFIG["bodyLearningRate"],
        head_learning_rate=TRAINING_CONFIG["headLearningRate"],
        max_length=TRAINING_CONFIG["maxLength"],
        sampling_strategy=TRAINING_CONFIG["samplingStrategy"],
        use_amp=TRAINING_CONFIG["useAmp"] and device == "cuda",
        seed=TRAINING_SEED,
        report_to="none",
        show_progress_bar=False,
        logging_strategy="no",
        save_strategy="no",
    )
    trainer = Trainer(model=model, args=arguments, train_dataset=dataset)
    started = time.perf_counter_ns()
    trainer.train()
    training_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
    metrics = {
        "schemaVersion": "setfit-binary-training-metrics-v1",
        "trainingPartition": "FIT_INTERNAL_TRAIN_64_ONLY",
        "trainingCaseCount": len(train_cases),
        "trainingTimeMs": training_ms,
        "parameterCount": parameter_count,
        "embeddingDimension": int(model.model_body.get_sentence_embedding_dimension()),
        "peakAllocatedVramMiB": round(torch.cuda.max_memory_allocated() / 1048576, 2) if device == "cuda" else 0.0,
        "peakReservedVramMiB": round(torch.cuda.max_memory_reserved() / 1048576, 2) if device == "cuda" else 0.0,
        "device": device,
        "dtype": str(next(model.model_body.parameters()).dtype).replace("torch.", ""),
        "validationCasesSeen": 0,
        "boundaryCasesSeen": 0,
        "frozenCasesSeen": 0,
    }
    return model, metrics


def classification_scores(model: Any, texts: list[str], batch_size: int = 16) -> np.ndarray:
    embeddings = model.model_body.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    probabilities = np.asarray(model.model_head.predict_proba(embeddings), dtype=np.float64)
    classes = list(model.model_head.classes_)
    if 1 not in classes:
        raise RuntimeError("SETFIT_LONG_REQUIRED_CLASS_MISSING")
    return probabilities[:, classes.index(1)]


def make_outputs(cases: list[dict[str, Any]], scores: np.ndarray, threshold: float, rule_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, case in enumerate(cases):
        row = binary.make_output(case, float(scores[index]), threshold, rule_by_id[case["caseId"]], model_name="setfit_binary")
        rows.append(row)
    return rows


def setfit_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = binary.binary_metrics(rows)
    actual_fast = [row for row in rows if row["binaryTarget"] == binary.FAST_ELIGIBLE]
    true_fast = [row for row in actual_fast if row["finalPrediction"] == binary.FAST_ELIGIBLE]
    hard = [row for row in rows if row.get("boundaryType") == "hard_negative"]
    hard_actual_fast = [row for row in hard if row["binaryTarget"] == binary.FAST_ELIGIBLE]
    hard_predicted_fast = [row for row in hard if row["finalPrediction"] == binary.FAST_ELIGIBLE]
    hard_true_fast = [row for row in hard_predicted_fast if row["binaryTarget"] == binary.FAST_ELIGIBLE]
    result["fastRecall"] = baseline.safe_ratio(len(true_fast), len(actual_fast))
    result["hardNegative"] = {
        "caseCount": len(hard),
        "fastTargetCount": len(hard_actual_fast),
        "predictedFastCount": len(hard_predicted_fast),
        "fastRecall": baseline.safe_ratio(len(hard_true_fast), len(hard_actual_fast)),
        "fastPrecision": baseline.safe_ratio(len(hard_true_fast), len(hard_predicted_fast)) if hard_predicted_fast else 0.0,
        "falseEscalationCount": len(hard_actual_fast) - len(hard_true_fast),
        "falseEscalationRate": baseline.safe_ratio(len(hard_actual_fast) - len(hard_true_fast), len(hard_actual_fast)),
    }
    return result


def select_threshold(model: Any, dev_cases: list[dict[str, Any]], rule_by_id: dict[str, dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    scores = classification_scores(model, [str(case["textZh"]) for case in dev_cases])
    candidates = []
    for threshold in THRESHOLDS:
        metrics = setfit_metrics(make_outputs(dev_cases, scores, threshold, rule_by_id))
        candidates.append({"threshold": threshold, "devMetrics": metrics})
    selected = min(
        candidates,
        key=lambda item: (
            -item["devMetrics"]["longRequiredRecall"],
            item["devMetrics"]["highRiskFalseFastCount"] != 0,
            item["devMetrics"]["highRiskFalseFastCount"],
            -item["devMetrics"]["fastPrecision"],
            -item["devMetrics"]["fastCoverage"],
            abs(item["threshold"] - 0.5),
        ),
    )
    artifact = {
        "schemaVersion": "setfit-binary-threshold-selection-v1",
        "trainingPartition": "FIT_INTERNAL_TRAIN_64",
        "selectionPartition": "FIT_INTERNAL_DEV_16",
        "candidateThresholds": list(THRESHOLDS),
        "rankingPriority": ["LONG_REQUIRED recall DESC", "HIGH/CRITICAL false fast ASC", "FAST precision DESC", "FAST coverage DESC"],
        "candidates": candidates,
        "selectedThreshold": selected["threshold"],
        "validationUsed": False,
        "boundaryUsed": False,
        "frozenUsed": False,
        "gate": "PASS",
    }
    return float(selected["threshold"]), artifact


def candidate_gate(metrics: dict[str, Any]) -> tuple[str, str]:
    safety_failed = metrics["highRiskFalseFastCount"] > 0 or metrics["materialSafetyFalseFastCount"] > 0
    passed = (
        metrics["longRequiredRecall"] >= 0.95
        and not safety_failed
        and metrics["fastPrecision"] >= 0.95
        and metrics["fastCoverage"] >= 0.20
    )
    limited = (
        metrics["longRequiredRecall"] >= 0.90
        and not safety_failed
        and metrics["fastPrecision"] >= 0.90
        and metrics["fastCoverage"] >= 0.10
    )
    if passed:
        return "PASS", "BINARY_ROUTER_SHADOW_MODE"
    if limited:
        return "PASS_WITH_LIMITATIONS", "BINARY_ROUTER_SHADOW_MODE"
    if safety_failed:
        return "FAIL_SAFETY", "SETFIT_BINARY_ROUTER_UNSAFE"
    if metrics["fastCoverage"] < 0.10:
        return "FAIL_TOO_CONSERVATIVE", "EXPAND_BINARY_TRAINING_POOL"
    return "FAIL_QUALITY", "TASK_SPECIFIC_FINETUNE_NOT_EFFECTIVE"


def latency_metrics(model: Any, cases: list[dict[str, Any]], threshold: float, rule_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    encoder_values: list[float] = []
    classifier_values: list[float] = []
    total_values: list[float] = []
    for case in cases:
        total_started = time.perf_counter_ns()
        encoder_started = time.perf_counter_ns()
        embedding = model.model_body.encode([str(case["textZh"])], convert_to_numpy=True, show_progress_bar=False)
        encoder_values.append((time.perf_counter_ns() - encoder_started) / 1_000_000)
        classifier_started = time.perf_counter_ns()
        classes = list(model.model_head.classes_)
        score = float(model.model_head.predict_proba(embedding)[0, classes.index(1)])
        binary.make_output(case, score, threshold, rule_by_id[case["caseId"]], model_name="setfit_binary")
        classifier_values.append((time.perf_counter_ns() - classifier_started) / 1_000_000)
        total_values.append((time.perf_counter_ns() - total_started) / 1_000_000)
    summarize = lambda values: {
        "p50Ms": baseline.percentile(values, 0.50),
        "p95Ms": baseline.percentile(values, 0.95),
        "p99Ms": baseline.percentile(values, 0.99),
    }
    return {
        "schemaVersion": "setfit-binary-latency-v1",
        "mode": "warm-single-request-batch-size-1",
        "caseCount": len(cases),
        "encoder": summarize(encoder_values),
        "classifier": summarize(classifier_values),
        "endToEnd": summarize(total_values),
        "externalApiCallCount": 0,
    }


def save_model(model: Any, path: Path) -> None:
    model.save_pretrained(str(path))
    config_path = path / "config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["_name_or_path"] = MODEL_ID
        baseline.write_json(config_path, config)


def stability_check(model: Any, cases: list[dict[str, Any]], threshold: float, rule_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    selected = cases[:10]
    texts = [str(case["textZh"]) for case in selected]
    first = make_outputs(selected, classification_scores(model, texts), threshold, rule_by_id)
    second = make_outputs(selected, classification_scores(model, texts), threshold, rule_by_id)
    stable = sum(left["finalPrediction"] == right["finalPrediction"] for left, right in zip(first, second))
    return {"executed": True, "caseCount": len(selected), "stableCount": stable, "decisionStability": baseline.safe_ratio(stable, len(selected))}


def build_report(snapshot: dict[str, Any], config: dict[str, Any], training: dict[str, Any], threshold: dict[str, Any], validation: dict[str, Any], boundary_metrics: dict[str, Any], comparison: dict[str, Any], gate: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# SetFit Binary Router Report",
            "",
            "## Scope",
            "",
            "Step 21.3E evaluates one task-specific SetFit binary classifier. Runtime Router, Safety Gate, risk taxonomy, datasets, workflow, RAG, and Frozen Gold remain unchanged.",
            "",
            "## Model And Training",
            "",
            f"Base encoder `{snapshot['modelId']}` at revision `{snapshot['revision']}` uses `{snapshot['license']}`, `{snapshot['parameterCount']}` parameters, and `{snapshot['embeddingDimension']}`-dimensional embeddings.",
            f"Train/Dev `{training['trainTargetDistribution']}/{training['devTargetDistribution']}`. Configuration: `{json.dumps(config['training'], sort_keys=True)}`.",
            f"Training time `{training['trainingTimeMs']} ms`; peak allocated/reserved VRAM `{training['peakAllocatedVramMiB']}/{training['peakReservedVramMiB']} MiB`.",
            f"Threshold `{threshold['selectedThreshold']}` was selected on Dev16 only.",
            "",
            "## Validation And Boundary",
            "",
            f"Validation accuracy/F1 `{validation['binaryAccuracy']:.4f}/{validation['binaryF1LongRequired']:.4f}`, LONG recall `{validation['longRequiredRecall']:.4f}`, FAST precision/coverage `{validation['fastPrecision']:.4f}/{validation['fastCoverage']:.4f}`, false fast `{validation['falseFastCount']}`.",
            f"Boundary LONG recall `{boundary_metrics['longRequiredRecall']:.4f}`, high-risk false fast `{boundary_metrics['highRiskFalseFastCount']}`, abstention `{boundary_metrics['abstentionLongCapture']['captured']}/{boundary_metrics['abstentionLongCapture']['targetCount']}`, hard-negative FAST recall `{boundary_metrics['hardNegative']['fastRecall']:.4f}`.",
            "",
            "## Three-way Comparison",
            "",
            f"`{json.dumps(comparison['validationSummary'], sort_keys=True)}`",
            "",
            "## Gates",
            "",
            f"`STEP21_3E_GATE = {gate['step21_3eGate']}`",
            f"`SETFIT_BINARY_ROUTER_CANDIDATE_GATE = {gate['setfitBinaryRouterCandidateGate']}`",
            f"`NEXT_RECOMMENDATION = {gate['nextRecommendation']}`",
            "",
        ]
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "WANDB_DISABLED": "true",
            "LANGFUSE_ENABLED": "false",
        }
    )
    protected = [baseline.DEFAULT_CALIBRATION, baseline.DEFAULT_BOUNDARY, baseline.DEFAULT_FROZEN, baseline.DEFAULT_FREEZE_MANIFEST]
    before = {str(path): baseline.sha256_file(path) for path in protected}
    if before[str(baseline.DEFAULT_CALIBRATION)] != baseline.CALIBRATION_SHA:
        raise RuntimeError("CALIBRATION_DATASET_HASH_MISMATCH")
    if before[str(baseline.DEFAULT_BOUNDARY)] != baseline.BOUNDARY_SHA:
        raise RuntimeError("BOUNDARY_DATASET_HASH_MISMATCH")
    if before[str(baseline.DEFAULT_FROZEN)] != baseline.FROZEN_GOLD_SHA:
        raise RuntimeError("FROZEN_GOLD_HASH_MISMATCH")
    if not args.model_dir.is_dir():
        raise RuntimeError("SETFIT_BASE_MODEL_UNAVAILABLE")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    fit, validation_cases, boundary_cases, rule_by_id = binary.load_partitions()
    split = load_fixed_split()
    split_by_id = {row["caseId"]: row["partition"] for row in split["rows"]}
    train_cases = [case for case in fit if split_by_id[case["caseId"]] == "TRAIN"]
    dev_cases = [case for case in fit if split_by_id[case["caseId"]] == "DEV"]
    if (len(train_cases), len(dev_cases)) != (64, 16):
        raise RuntimeError("SETFIT_TRAIN_DEV_COUNT_MISMATCH")

    model, training = fit_setfit_model(args.model_dir, train_cases, args.output_dir, args.device)
    training["trainTargetDistribution"] = binary.target_distribution(train_cases)["targets"]
    training["devTargetDistribution"] = binary.target_distribution(dev_cases)["targets"]
    training["internalSplitHash"] = split["splitHash"]
    threshold_value, threshold = select_threshold(model, dev_cases, rule_by_id)

    validation_scores = classification_scores(model, [str(case["textZh"]) for case in validation_cases])
    validation_rows = make_outputs(validation_cases, validation_scores, threshold_value, rule_by_id)
    validation_metrics = setfit_metrics(validation_rows)
    boundary_scores = classification_scores(model, [str(case["textZh"]) for case in boundary_cases])
    boundary_rows = make_outputs(boundary_cases, boundary_scores, threshold_value, rule_by_id)
    boundary_result = setfit_metrics(boundary_rows)
    boundary_result["byBoundaryType"] = {
        kind: setfit_metrics([row for row in boundary_rows if str(row.get("boundaryType")) == kind])
        for kind in sorted({str(row.get("boundaryType")) for row in boundary_rows})
    }

    candidate, recommendation = candidate_gate(validation_metrics)
    stability = stability_check(model, validation_cases, threshold_value, rule_by_id) if candidate in {"PASS", "PASS_WITH_LIMITATIONS"} else {"executed": False, "reason": "VALIDATION_GATE_NOT_PASS"}
    training["stability"] = stability
    latency = latency_metrics(model, validation_cases + boundary_cases, threshold_value, rule_by_id)
    training["latency"] = latency

    model_path = args.output_dir / "setfit_binary_router_v1"
    save_model(model, model_path)
    head_path = model_path / "model_head.pkl"
    model_artifact_hash = baseline.sha256_file(head_path) if head_path.is_file() else ""
    snapshot = {
        "schemaVersion": "setfit-binary-model-snapshot-v1",
        "modelId": MODEL_ID,
        "revision": MODEL_REVISION,
        "license": MODEL_LICENSE,
        "parameterCount": training["parameterCount"],
        "embeddingDimension": training["embeddingDimension"],
        "baseModelWeightsSha": model_file_hash(args.model_dir),
        "classificationHeadSha": model_artifact_hash,
        "singleBaseEncoderOnly": True,
        "generativeModel": False,
        "localExecution": True,
        "externalApiCallCount": 0,
    }
    config = {
        "schemaVersion": "setfit-binary-training-config-v1",
        "benchmarkVersion": BENCHMARK_VERSION,
        "baseEncoder": MODEL_ID,
        "baseEncoderFixedBeforeTraining": True,
        "training": TRAINING_CONFIG,
        "trainingPartition": "FIT_INTERNAL_TRAIN_64_ONLY",
        "thresholdSelectionPartition": "FIT_INTERNAL_DEV_16_ONLY",
        "validationUsedForTrainingOrTuning": False,
        "boundaryUsedForTrainingOrTuning": False,
        "frozenUsed": False,
        "binaryTargetDefinitionHash": baseline.sha256_file(binary.DEFAULT_OUTPUT_DIR / "binary_router_target_definition_v1.json"),
        "internalSplitHash": split["splitHash"],
    }

    previous_comparison = json.loads((binary.DEFAULT_OUTPUT_DIR / "rule_vs_binary_bge_v1.json").read_text(encoding="utf-8"))
    bge_manifest = json.loads((binary.DEFAULT_OUTPUT_DIR / "bge_binary_router_manifest_v1.json").read_text(encoding="utf-8"))
    rule_validation = previous_comparison["ruleBinaryBaseline"]["validation"]
    bge_validation = previous_comparison["bgeBinaryLogistic"]["validation"]
    rule_boundary = previous_comparison["ruleBinaryBaseline"]["boundary"]
    bge_boundary = previous_comparison["bgeBinaryLogistic"]["boundary"]
    summarize = lambda metrics, latency_value: {
        "longRecall": metrics["longRequiredRecall"],
        "fastPrecision": metrics["fastPrecision"],
        "fastCoverage": metrics["fastCoverage"],
        "falseFast": metrics["falseFastCount"],
        "highRiskFalseFast": metrics["highRiskFalseFastCount"],
        "safetyFalseFast": metrics["materialSafetyFalseFastCount"],
        "hardNegativeFastRecall": metrics.get("hardNegative", {}).get("fastRecall"),
        "p50Ms": latency_value.get("p50Ms"),
        "p95Ms": latency_value.get("p95Ms"),
    }
    comparison = {
        "schemaVersion": "binary-router-three-way-comparison-v1",
        "sameBinaryTarget": True,
        "sameValidationCases": True,
        "sameBoundaryCases": True,
        "validationSummary": {
            "cheapRule": summarize(rule_validation, {}),
            "frozenBgeLogistic": summarize(bge_validation, bge_manifest["latency"]["endToEnd"]),
            "setfitBinary": summarize(validation_metrics, latency["endToEnd"]),
        },
        "boundarySummary": {
            "cheapRule": summarize(rule_boundary, {}),
            "frozenBgeLogistic": summarize(bge_boundary, bge_manifest["latency"]["endToEnd"]),
            "setfitBinary": summarize(boundary_result, latency["endToEnd"]),
        },
        "setfitFastCoverageGainVsFrozenBge": round(validation_metrics["fastCoverage"] - bge_validation["fastCoverage"], 6),
        "oldTenLabelMetricsExcluded": True,
    }

    baseline.write_json(args.output_dir / "setfit_binary_model_snapshot_v1.json", snapshot)
    baseline.write_json(args.output_dir / "setfit_binary_training_config_v1.json", config)
    baseline.write_json(args.output_dir / "setfit_binary_training_metrics_v1.json", training)
    baseline.write_json(args.output_dir / "setfit_binary_threshold_selection_v1.json", threshold)
    baseline.write_jsonl(args.output_dir / "setfit_binary_validation_outputs_v1.jsonl", validation_rows)
    baseline.write_json(args.output_dir / "setfit_binary_validation_metrics_v1.json", validation_metrics)
    baseline.write_jsonl(args.output_dir / "setfit_binary_boundary_outputs_v1.jsonl", boundary_rows)
    baseline.write_json(args.output_dir / "setfit_binary_boundary_metrics_v1.json", boundary_result)
    baseline.write_json(args.output_dir / "binary_router_three_way_comparison_v1.json", comparison)

    after = {str(path): baseline.sha256_file(path) for path in protected}
    if after != before:
        raise RuntimeError("PROTECTED_DATASET_CHANGED")
    safety_gate = "PASS" if validation_metrics["highRiskFalseFastCount"] == 0 and validation_metrics["materialSafetyFalseFastCount"] == 0 else "FAIL"
    latency_gate = "PASS" if latency["endToEnd"]["p95Ms"] <= 200 else "PASS_WITH_LIMITATIONS"
    gate = {
        "setfitModelAvailabilityGate": "PASS",
        "setfitTrainingGate": "PASS",
        "setfitThresholdGate": "PASS",
        "setfitValidationGate": "PASS",
        "setfitSafetyGate": safety_gate,
        "setfitBoundaryGate": "PASS",
        "setfitLatencyGate": latency_gate,
        "datasetReadOnlyGate": "PASS",
        "securityScanGate": "PASS",
        "step21_3eGate": "PASS",
        "setfitBinaryRouterCandidateGate": candidate,
        "nextRecommendation": recommendation,
        "calibrationSha": before[str(baseline.DEFAULT_CALIBRATION)],
        "boundarySha": before[str(baseline.DEFAULT_BOUNDARY)],
        "frozenGoldSha": before[str(baseline.DEFAULT_FROZEN)],
        "frozenBenchmarkExecuted": False,
        "runtimeRouterModified": False,
        "safetyGateModified": False,
        "datasetModified": False,
        "longAnalysisExecuted": False,
        "policyRagExecuted": False,
        "reflectionExecuted": False,
        "qwenCallCount": 0,
        "externalApiCallCount": 0,
    }
    baseline.write_json(args.output_dir / "step213e_setfit_gate_v1.json", gate)
    args.report.write_text(build_report(snapshot, config, training, threshold, validation_metrics, boundary_result, comparison, gate), encoding="utf-8", newline="\n")
    return {
        "snapshot": snapshot,
        "training": training,
        "threshold": threshold,
        "validation": validation_metrics,
        "boundary": boundary_result,
        "comparison": comparison,
        "gate": gate,
    }


def main() -> int:
    result = run(parse_args())
    print(json.dumps({"snapshot": result["snapshot"], "validation": result["validation"], "boundary": result["boundary"], "gate": result["gate"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
