from __future__ import annotations

"""Run the offline Step 21.3A.2 BGE-M3 + logistic-router baseline."""

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.embedding_provider import BgeM3EmbeddingProvider, BgeM3EmbeddingProviderConfig
from app.risk_calibration.severity import RiskSeverityEvaluator
from scripts import run_step213a_lite as qwen_base
from scripts import run_step213a1_gpu_qwen_benchmark as gpu_qwen
from scripts import run_step2123_reliability_analysis as baseline


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "step213a2_discriminative"
DEFAULT_REPORT = REPO_ROOT / "docs" / "DISCRIMINATIVE_ROUTER_BENCHMARK_REPORT.md"
DEFAULT_MODEL_DIR = ROOT.parents[1] / "models" / "bge-m3"
MODEL_ID = "BAAI/bge-m3"
BENCHMARK_VERSION = "step21.3a.2-bge-m3-logistic-v1"
INTERNAL_SPLIT_SEED = "step21.3a.2-fit64-dev16-v1"
RANDOM_STATE = 2132
THRESHOLDS = (0.30, 0.40, 0.50, 0.60)
LABELS = (
    "normal_review",
    "negative_review",
    "after_sales_risk",
    "fake_review",
    "paid_review",
    "rating_manipulation",
    "review_suppression",
    "safety_or_fraud_risk",
    "harassment_or_abuse",
    "privacy_risk",
)
LR_PARAMETERS = {
    "penalty": "l2",
    "C": 1.0,
    "class_weight": "balanced",
    "max_iter": 1000,
    "random_state": RANDOM_STATE,
    "solver": "liblinear",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    return parser.parse_args()


def stable_json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def load_partitions() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    split = json.loads(qwen_base.DEFAULT_SPLIT.read_text(encoding="utf-8"))
    split_by_id = {row["caseId"]: row["partition"] for row in split["rows"]}
    calibration = qwen_base.load_jsonl(qwen_base.DEFAULT_CALIBRATION)
    fit = [dict(row, _partition="FIT") for row in calibration if split_by_id.get(row["caseId"]) == "FIT"]
    validation = [dict(row, _partition="VALIDATION") for row in calibration if split_by_id.get(row["caseId"]) == "VALIDATION"]
    boundary = [dict(row, _partition="BOUNDARY_CHALLENGE") for row in qwen_base.load_jsonl(qwen_base.DEFAULT_BOUNDARY)]
    rule_rows = {
        row["caseId"]: row
        for row in qwen_base.load_jsonl(qwen_base.DEFAULT_RULE_RESULTS)
        if row["partition"] in {"VALIDATION", "BOUNDARY_CHALLENGE"}
    }
    if (len(fit), len(validation), len(boundary), len(rule_rows)) != (80, 40, 60, 100):
        raise RuntimeError("DATASET_PARTITION_COUNT_MISMATCH")
    return fit, validation, boundary, rule_rows


def multilabel_encode(cases: list[dict[str, Any]]) -> np.ndarray:
    matrix = np.zeros((len(cases), len(LABELS)), dtype=np.int8)
    label_index = {label: index for index, label in enumerate(LABELS)}
    for row_index, case in enumerate(cases):
        for label in qwen_base.expected_risks(case):
            if label not in label_index:
                raise ValueError(f"UNSUPPORTED_TRAINING_LABEL:{label}")
            matrix[row_index, label_index[label]] = 1
    return matrix


def label_support(cases: list[dict[str, Any]]) -> dict[str, Any]:
    encoded = multilabel_encode(cases)
    rows = []
    for index, label in enumerate(LABELS):
        positive = int(encoded[:, index].sum())
        status = "UNTRAINABLE_NO_POSITIVE" if positive == 0 else "RARE_CLASS_LIMITATION" if positive <= 2 else "TRAINABLE"
        rows.append({"riskType": label, "positiveCount": positive, "negativeCount": len(cases) - positive, "status": status})
    statuses = {row["status"] for row in rows}
    gate = "FAIL" if "UNTRAINABLE_NO_POSITIVE" in statuses else "PASS_WITH_LIMITATIONS" if "RARE_CLASS_LIMITATION" in statuses else "PASS"
    return {"schemaVersion": "discriminative-label-support-v1", "partition": "CALIBRATION_FIT_80", "caseCount": len(cases), "labels": rows, "gate": gate}


def _split_features(case: dict[str, Any]) -> set[str]:
    risks = qwen_base.expected_risks(case)
    return {
        *(f"risk:{risk}" for risk in risks),
        f"source:{case.get('sourceDataset', 'unknown')}",
        f"expression:{case.get('expressionType', 'unknown')}",
        f"difficulty:{case.get('difficulty', 'unknown')}",
        f"multi:{bool(case.get('multiRisk'))}",
    }


def internal_split(fit_cases: list[dict[str, Any]], dev_count: int = 16) -> dict[str, Any]:
    feature_counts = Counter(feature for case in fit_cases for feature in _split_features(case))
    targets = {feature: count * dev_count / len(fit_cases) for feature, count in feature_counts.items()}
    selected_counts: Counter[str] = Counter()
    remaining = {case["caseId"]: case for case in fit_cases}
    dev_ids: set[str] = set()

    def improvement(case: dict[str, Any]) -> float:
        score = 0.0
        for feature in _split_features(case):
            target = targets[feature]
            current = selected_counts[feature]
            score += ((current - target) ** 2 - (current + 1 - target) ** 2) / max(target, 1.0)
        return score

    while len(dev_ids) < dev_count:
        candidates = []
        for case in remaining.values():
            rare_positive = any(feature.startswith("risk:") and feature_counts[feature] == 1 for feature in _split_features(case))
            if not rare_positive:
                candidates.append(case)
        if not candidates:
            candidates = list(remaining.values())
        chosen = sorted(candidates, key=lambda case: (-improvement(case), baseline.stable_hash(f"{INTERNAL_SPLIT_SEED}|{case['caseId']}")))[0]
        dev_ids.add(chosen["caseId"])
        selected_counts.update(_split_features(chosen))
        del remaining[chosen["caseId"]]
    rows = [{"caseId": case["caseId"], "partition": "DEV" if case["caseId"] in dev_ids else "TRAIN"} for case in fit_cases]
    return {
        "schemaVersion": "discriminative-internal-split-v1",
        "seed": INTERNAL_SPLIT_SEED,
        "method": "deterministic-multivariate-greedy-stratification",
        "sourcePartition": "CALIBRATION_FIT_80",
        "counts": {"TRAIN": 64, "DEV": 16},
        "rows": rows,
        "splitHash": stable_json_hash(rows),
    }


def fit_heads(vectors: np.ndarray, targets: np.ndarray) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    heads: dict[str, Any] = {}
    status: list[dict[str, Any]] = []
    for index, label in enumerate(LABELS):
        values = targets[:, index].astype(int)
        unique = sorted(set(values.tolist()))
        if len(unique) < 2:
            heads[label] = {"type": "constant", "value": float(unique[0])}
            status.append({"riskType": label, "type": "constant", "status": "UNTRAINABLE_LABEL", "constantValue": int(unique[0])})
            continue
        model = LogisticRegression(**LR_PARAMETERS)
        model.fit(vectors, values)
        heads[label] = model
        status.append({"riskType": label, "type": "logistic_regression", "status": "TRAINED"})
    return {"labels": list(LABELS), "heads": heads, "parameters": LR_PARAMETERS}, status


def predict_scores(model: dict[str, Any], vectors: np.ndarray) -> np.ndarray:
    columns = []
    for label in LABELS:
        head = model["heads"][label]
        if isinstance(head, dict):
            columns.append(np.full(vectors.shape[0], float(head["value"]), dtype=np.float64))
        else:
            columns.append(head.predict_proba(vectors)[:, 1])
    return np.column_stack(columns).astype(np.float64)


def postprocess_scores(scores: np.ndarray, threshold: float) -> tuple[str, list[str]]:
    non_normal = [LABELS[index] for index in range(1, len(LABELS)) if float(scores[index]) >= threshold]
    if non_normal:
        return "CLASSIFY", non_normal
    if float(scores[0]) >= threshold:
        return "CLASSIFY", ["normal_review"]
    return "ABSTAIN", []


def classification_row(case: dict[str, Any], scores: np.ndarray, threshold: float) -> dict[str, Any]:
    decision, predicted = postprocess_scores(scores, threshold)
    expected = qwen_base.expected_risks(case)
    target = str(case.get("evaluationTarget") or "RISK_CLASSIFICATION").upper()
    exact = target != "ABSTENTION" and predicted == expected
    abstention_correct = target == "ABSTENTION" and decision == "ABSTAIN"
    material_error, missing_material = baseline.is_material_safety_error(expected, predicted)
    expected_set, predicted_set = set(expected), set(predicted)
    tp = len(expected_set & predicted_set)
    precision = baseline.safe_ratio(tp, len(predicted_set)) if target != "ABSTENTION" else None
    recall = baseline.safe_ratio(tp, len(expected_set)) if target != "ABSTENTION" else None
    f1 = baseline.safe_ratio(2 * precision * recall, precision + recall) if precision is not None and recall is not None and precision + recall else (0.0 if target != "ABSTENTION" else None)
    ordered = sorted((float(value) for value in scores), reverse=True)
    max_score = ordered[0]
    second_score = ordered[1]
    severity = RiskSeverityEvaluator().evaluate(predicted or ["normal_review"], review_text=str(case["textZh"]))
    return {
        "schemaVersion": "bge-logistic-router-output-v1",
        "caseId": case["caseId"],
        "datasetPartition": case["_partition"],
        "evaluationTarget": target,
        "expectedRiskTypes": expected,
        "predictedRiskTypes": predicted,
        "decision": decision,
        "predictedSeverity": severity.severity,
        "severityReasonCodes": list(severity.severityReasons),
        "classificationScores": {label: round(float(scores[index]), 6) for index, label in enumerate(LABELS)},
        "scoreSignals": {"maxScore": round(max_score, 6), "secondScore": round(second_score, 6), "top1Top2Margin": round(max_score - second_score, 6), "predictedLabelCount": len(predicted)},
        "threshold": threshold,
        "exactMatch": exact,
        "riskTypePrecision": precision,
        "riskTypeRecall": recall,
        "riskTypeF1": f1,
        "abstentionCorrect": abstention_correct,
        "falseConfidentClassification": target == "ABSTENTION" and decision == "CLASSIFY" and max_score >= 0.8,
        "outcomeCorrect": exact or abstention_correct,
        "materialSafetyError": material_error,
        "missingMaterialRiskTypes": missing_material,
        "highRiskMiss": material_error,
        "highRiskAutoPassCandidate": material_error and predicted == ["normal_review"],
        "sourceDataset": case.get("sourceDataset"),
        "expressionType": case.get("expressionType"),
        "difficulty": case.get("difficulty"),
        "multiRisk": bool(case.get("multiRisk")),
        "boundaryType": case.get("boundaryType"),
        "excludeFromRiskTypeMetrics": bool(case.get("excludeFromRiskTypeMetrics")),
    }


def evaluate_cases(cases: list[dict[str, Any]], scores: np.ndarray, threshold: float) -> list[dict[str, Any]]:
    return [classification_row(case, scores[index], threshold) for index, case in enumerate(cases)]


def multilabel_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scoped = [row for row in rows if row["evaluationTarget"] != "ABSTENTION" and not row["excludeFromRiskTypeMetrics"]]
    tp = fp = fn = 0
    per_label = {}
    for label in LABELS:
        ltp = sum(label in row["expectedRiskTypes"] and label in row["predictedRiskTypes"] for row in scoped)
        lfp = sum(label not in row["expectedRiskTypes"] and label in row["predictedRiskTypes"] for row in scoped)
        lfn = sum(label in row["expectedRiskTypes"] and label not in row["predictedRiskTypes"] for row in scoped)
        precision = baseline.safe_ratio(ltp, ltp + lfp)
        recall = baseline.safe_ratio(ltp, ltp + lfn)
        per_label[label] = {"support": ltp + lfn, "precision": precision, "recall": recall, "f1": baseline.safe_ratio(2 * precision * recall, precision + recall)}
        tp += ltp
        fp += lfp
        fn += lfn
    precision = baseline.safe_ratio(tp, tp + fp)
    recall = baseline.safe_ratio(tp, tp + fn)
    return {
        "caseCount": len(scoped),
        "exactSetMatchAccuracy": baseline.safe_ratio(sum(row["exactMatch"] for row in scoped), len(scoped)),
        "microPrecision": precision,
        "microRecall": recall,
        "microF1": baseline.safe_ratio(2 * precision * recall, precision + recall),
        "macroF1": round(sum(item["f1"] for item in per_label.values()) / len(LABELS), 6),
        "perLabel": per_label,
    }


def subset_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = multilabel_metrics(rows)
    return {"caseCount": len(rows), "exactAccuracy": values["exactSetMatchAccuracy"], "microF1": values["microF1"]}


def quality_metrics(validation_rows: list[dict[str, Any]], boundary_rows: list[dict[str, Any]], trainable_labels: list[str]) -> dict[str, Any]:
    combined = validation_rows + boundary_rows
    selectors = {
        "singleRisk": lambda row: not row["multiRisk"] and row["evaluationTarget"] != "ABSTENTION",
        "multiRisk": lambda row: row["multiRisk"] and row["evaluationTarget"] != "ABSTENTION",
        "normalReview": lambda row: row["expectedRiskTypes"] == ["normal_review"],
        "hard": lambda row: row["difficulty"] == "hard" and row["evaluationTarget"] != "ABSTENTION",
        "explicit": lambda row: row["expressionType"] == "explicit" and row["evaluationTarget"] != "ABSTENTION",
        "implicit": lambda row: row["expressionType"] == "implicit" and row["evaluationTarget"] != "ABSTENTION",
        "mixed": lambda row: row["expressionType"] == "mixed" and row["evaluationTarget"] != "ABSTENTION",
    }
    combined_metrics = multilabel_metrics(combined)
    per_label = combined_metrics["perLabel"]
    trainable_macro = round(sum(per_label[label]["f1"] for label in trainable_labels) / len(trainable_labels), 6) if trainable_labels else 0.0
    boundary_types = ("implicit_or_paraphrase", "lexical_mismatch", "hard_negative", "multi_risk_or_conflict", "ambiguous_context", "noisy_or_adversarial")
    abstention = [row for row in boundary_rows if row["evaluationTarget"] == "ABSTENTION"]
    non_abstention = [row for row in combined if row["evaluationTarget"] != "ABSTENTION"]
    return {
        "schemaVersion": "bge-logistic-quality-metrics-v1",
        "validation": multilabel_metrics(validation_rows),
        "boundary": {"overall": multilabel_metrics(boundary_rows), "byType": {kind: subset_metrics([row for row in boundary_rows if row["boundaryType"] == kind]) for kind in boundary_types}},
        "combined": combined_metrics,
        "trainableLabelMacroF1": trainable_macro,
        "slices": {name: subset_metrics([row for row in combined if selector(row)]) for name, selector in selectors.items()},
        "abstention": {
            "caseCount": len(abstention),
            "accuracy": baseline.safe_ratio(sum(row["abstentionCorrect"] for row in abstention), len(abstention)),
            "falseConfidentClassificationCount": sum(row["falseConfidentClassification"] for row in abstention),
            "overAbstentionRate": baseline.safe_ratio(sum(row["decision"] == "ABSTAIN" for row in non_abstention), len(non_abstention)),
        },
    }


def safety_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": "bge-logistic-safety-metrics-v1",
        "caseCount": len(rows),
        "materialSafetyErrorCount": sum(row["materialSafetyError"] for row in rows),
        "highRiskMissCount": sum(row["highRiskMiss"] for row in rows),
        "highRiskAutoPassCandidateCount": sum(row["highRiskAutoPassCandidate"] for row in rows),
        "materialSafetyDefinition": "Step21.2.3 BASE_SEVERITY >= HIGH missing from predicted set",
    }


def multi_risk_recall(rows: list[dict[str, Any]]) -> float:
    multi = [row for row in rows if row["multiRisk"] and row["evaluationTarget"] != "ABSTENTION"]
    expected = sum(len(row["expectedRiskTypes"]) for row in multi)
    matched = sum(len(set(row["expectedRiskTypes"]) & set(row["predictedRiskTypes"])) for row in multi)
    return baseline.safe_ratio(matched, expected)


def select_threshold(train_vectors: np.ndarray, train_cases: list[dict[str, Any]], dev_vectors: np.ndarray, dev_cases: list[dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    started = time.perf_counter_ns()
    model, head_status = fit_heads(train_vectors, multilabel_encode(train_cases))
    training_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
    scores = predict_scores(model, dev_vectors)
    candidates = []
    for threshold in THRESHOLDS:
        rows = evaluate_cases(dev_cases, scores, threshold)
        metrics = multilabel_metrics(rows)
        candidates.append({
            "threshold": threshold,
            "materialSafetyErrorCount": sum(row["materialSafetyError"] for row in rows),
            "microF1": metrics["microF1"],
            "multiRiskRecall": multi_risk_recall(rows),
            "exactSetMatchAccuracy": metrics["exactSetMatchAccuracy"],
        })
    ranked = sorted(candidates, key=lambda item: (item["materialSafetyErrorCount"], -item["microF1"], -item["multiRiskRecall"], abs(item["threshold"] - 0.5), item["threshold"]))
    selected = ranked[0]["threshold"]
    artifact = {
        "schemaVersion": "discriminative-threshold-selection-v1",
        "selectionPartition": "FIT_INTERNAL_DEV_16",
        "trainingPartition": "FIT_INTERNAL_TRAIN_64",
        "validationUsed": False,
        "boundaryUsed": False,
        "frozenUsed": False,
        "strategy": "single-global-threshold",
        "candidateThresholds": list(THRESHOLDS),
        "rankingPriority": ["materialSafetyErrorCount ASC", "microF1 DESC", "multiRiskRecall DESC", "distanceTo0.5 ASC"],
        "candidates": candidates,
        "selectedGlobalThreshold": selected,
        "internalTrainingTimeMs": training_ms,
        "headStatus": head_status,
        "gate": "PASS",
    }
    return selected, artifact


def cache_embeddings(provider: BgeM3EmbeddingProvider, cases: list[dict[str, Any]], output_dir: Path, model_hash: str) -> tuple[np.ndarray, dict[str, Any]]:
    cache_dir = output_dir / "embedding_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "bge_m3_embedding_cache_manifest_v1.json"
    previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    records = []
    vectors_by_id: dict[str, np.ndarray] = {}
    missing: list[tuple[dict[str, Any], Path, str, str]] = []
    normalization = {"method": "L2", "normalized": True, "wrapper": "BgeM3EmbeddingProvider._validate"}
    for case in cases:
        text_hash = hashlib.sha256(str(case["textZh"]).encode("utf-8")).hexdigest().upper()
        key = stable_json_hash({"caseId": case["caseId"], "textHash": text_hash, "embeddingModelId": MODEL_ID, "embeddingModelRevision": model_hash, "normalizationConfig": normalization})
        path = cache_dir / f"{key}.npy"
        if path.is_file():
            vector = np.load(path, allow_pickle=False).astype("float32")
            if vector.ndim == 1 and np.isclose(np.linalg.norm(vector), 1.0, atol=1e-3):
                vectors_by_id[case["caseId"]] = vector
                records.append({"caseId": case["caseId"], "partition": case["_partition"], "textHash": text_hash, "cacheKey": key, "cacheHit": True})
                continue
        missing.append((case, path, text_hash, key))
    started = time.perf_counter_ns()
    if missing:
        matrix = provider.encode_documents([str(item[0]["textZh"]) for item in missing])
        for index, (case, path, text_hash, key) in enumerate(missing):
            vector = matrix[index].astype("float32")
            np.save(path, vector, allow_pickle=False)
            vectors_by_id[case["caseId"]] = vector
            records.append({"caseId": case["caseId"], "partition": case["_partition"], "textHash": text_hash, "cacheKey": key, "cacheHit": False})
    current_run_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
    initial_extraction_ms = previous_manifest.get("embeddingExtractionTimeMs") if not missing else current_run_ms
    if initial_extraction_ms is None:
        initial_extraction_ms = current_run_ms
    ordered = np.stack([vectors_by_id[case["caseId"]] for case in cases]).astype("float32")
    records.sort(key=lambda item: next(index for index, case in enumerate(cases) if case["caseId"] == item["caseId"]))
    manifest = {
        "schemaVersion": "bge-m3-embedding-cache-manifest-v1",
        "modelId": MODEL_ID,
        "modelRevision": model_hash,
        "dimension": int(ordered.shape[1]),
        "normalizationConfig": normalization,
        "caseCount": len(cases),
        "cacheHitCount": sum(item["cacheHit"] for item in records),
        "cacheMissCount": sum(not item["cacheHit"] for item in records),
        "embeddingExtractionTimeMs": initial_extraction_ms,
        "currentRunCacheLookupTimeMs": current_run_ms,
        "records": records,
        "gate": "PASS",
    }
    return ordered, manifest


def latency_metrics(provider: BgeM3EmbeddingProvider, model: dict[str, Any], cases: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    embedding_values = []
    classifier_values = []
    total_values = []
    for case in cases:
        total_started = time.perf_counter_ns()
        embedding_started = time.perf_counter_ns()
        vector = provider.encode_documents([str(case["textZh"])])
        embedding_ms = (time.perf_counter_ns() - embedding_started) / 1_000_000
        classifier_started = time.perf_counter_ns()
        scores = predict_scores(model, vector)[0]
        postprocess_scores(scores, threshold)
        classifier_ms = (time.perf_counter_ns() - classifier_started) / 1_000_000
        total_ms = (time.perf_counter_ns() - total_started) / 1_000_000
        embedding_values.append(embedding_ms)
        classifier_values.append(classifier_ms)
        total_values.append(total_ms)
    summary = lambda values: {"p50Ms": baseline.percentile(values, 0.50), "p95Ms": baseline.percentile(values, 0.95), "p99Ms": baseline.percentile(values, 0.99)}
    return {"schemaVersion": "bge-logistic-latency-v1", "mode": "warm-single-request-batch-size-1", "caseCount": len(cases), "embedding": summary(embedding_values), "classifier": summary(classifier_values), "endToEnd": summary(total_values)}


def reliability_diagnostic(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    buckets = {
        "GE_0_8": lambda value: value >= 0.8,
        "GE_0_6_LT_0_8": lambda value: 0.6 <= value < 0.8,
        "GE_THRESHOLD_LT_0_6": lambda value: threshold <= value < 0.6,
    }
    result = {}
    for name, predicate in buckets.items():
        selected = [row for row in rows if predicate(row["scoreSignals"]["maxScore"])]
        result[name] = {
            "count": len(selected),
            "coverage": baseline.safe_ratio(len(selected), len(rows)),
            "accuracy": baseline.safe_ratio(sum(row["outcomeCorrect"] for row in selected), len(selected)) if selected else None,
            "materialSafetyErrorCount": sum(row["materialSafetyError"] for row in selected),
        }
    return {"schemaVersion": "bge-logistic-reliability-diagnostic-v1", "scoreInterpretation": "ordinal-classification-signal-not-calibrated-probability", "buckets": result}


def comparison_artifact(rule_validation: dict[str, Any], rule_boundary: dict[str, Any], rule_combined: dict[str, Any], quality: dict[str, Any], safety: dict[str, Any]) -> dict[str, Any]:
    bge = quality
    return {
        "schemaVersion": "rule-vs-bge-logistic-comparison-v1",
        "sameEvaluationCases": True,
        "rule": {"validation": rule_validation, "boundary": rule_boundary, "combined": rule_combined},
        "bgeM3Logistic": {
            "validation": bge["validation"],
            "boundary": bge["boundary"]["overall"],
            "combined": bge["combined"],
            "multiRisk": bge["slices"]["multiRisk"],
            "hard": bge["slices"]["hard"],
            "abstention": bge["abstention"],
            "safety": safety,
        },
        "gains": {
            "validationMicroF1": round(bge["validation"]["microF1"] - rule_validation["microF1"], 6),
            "boundaryMicroF1": round(bge["boundary"]["overall"]["microF1"] - rule_boundary["microF1"], 6),
            "multiRiskMicroF1": round(bge["slices"]["multiRisk"]["microF1"] - rule_combined["multiRiskMicroF1"], 6),
            "materialSafetyErrorReduction": rule_combined["materialSafetyErrorCount"] - safety["materialSafetyErrorCount"],
        },
    }


def build_report(manifest: dict[str, Any], support: dict[str, Any], threshold: dict[str, Any], quality: dict[str, Any], comparison: dict[str, Any], diagnostic: dict[str, Any], latency: dict[str, Any], gate: dict[str, Any]) -> str:
    rule = comparison["rule"]
    bge = comparison["bgeM3Logistic"]
    support_text = ", ".join(f"{row['riskType']}={row['positiveCount']}" for row in support["labels"])
    lines = [
        "# Discriminative Router Benchmark Report", "",
        "## Scope", "",
        "Step 21.3A.2 evaluates a frozen local BGE-M3 encoder with ten independent one-vs-rest logistic heads. It is offline-only: runtime Router, Safety Gate, Workflow, datasets, and Frozen Gold are unchanged.", "",
        "## Encoder And Training", "",
        f"- Encoder: `{manifest['embeddingModelId']}` / `{manifest['embeddingImplementation']}`.",
        f"- Device / dtype / dimension: `{manifest['device']}` / `{manifest['dtype']}` / `{manifest['embeddingDimension']}`.",
        f"- Frozen encoder trainable parameter tensors: `{manifest['trainableEncoderParameterTensors']}`.",
        f"- Fit label support: {support_text}.",
        f"- Global threshold selected on Fit-internal Dev only: `{threshold['selectedGlobalThreshold']}`.",
        f"- Final logistic training time: `{manifest['finalTrainingTimeMs']} ms`; embedding extraction: `{manifest['embeddingExtractionTimeMs']} ms`.", "",
        "## Rule Vs BGE-M3 Logistic", "",
        "| Metric | Rule | BGE-M3 + LR |", "| --- | ---: | ---: |",
        f"| Validation Exact | {rule['validation']['exactSetMatchAccuracy']:.4f} | {bge['validation']['exactSetMatchAccuracy']:.4f} |",
        f"| Validation Micro F1 | {rule['validation']['microF1']:.4f} | {bge['validation']['microF1']:.4f} |",
        f"| Boundary Micro F1 | {rule['boundary']['microF1']:.4f} | {bge['boundary']['microF1']:.4f} |",
        f"| Multi-risk Micro F1 | {rule['combined']['multiRiskMicroF1']:.4f} | {bge['multiRisk']['microF1']:.4f} |",
        f"| Material Safety Errors | {rule['combined']['materialSafetyErrorCount']} | {bge['safety']['materialSafetyErrorCount']} |", "",
        "## Abstention And Reliability", "",
        f"Abstention accuracy `{bge['abstention']['accuracy']:.4f}`. Scores are ordinal classification signals, not calibrated probabilities. Diagnostic: `{json.dumps(quality['reliabilityDiagnostic']['buckets'], sort_keys=True)}`.", "",
        "## Single Request Latency", "",
        f"Embedding P50/P95 `{latency['embedding']['p50Ms']}/{latency['embedding']['p95Ms']} ms`; classifier `{latency['classifier']['p50Ms']}/{latency['classifier']['p95Ms']} ms`; end-to-end `{latency['endToEnd']['p50Ms']}/{latency['endToEnd']['p95Ms']} ms`.", "",
        "## Integrity", "",
        f"Calibration SHA `{gate['calibrationSha']}`; Boundary SHA `{gate['boundarySha']}`; Frozen SHA `{gate['frozenGoldSha']}`. Frozen was not executed. External API calls: `0`.", "",
        "## Gates", "",
        *(f"- `{key}` = `{value}`" for key, value in gate.items() if key.endswith("Gate")), "",
        "## Conclusion", "",
        f"`{gate['nextRecommendation']}`", "",
    ]
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    import torch

    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"})
    protected = [qwen_base.DEFAULT_CALIBRATION, qwen_base.DEFAULT_BOUNDARY, qwen_base.DEFAULT_FROZEN, qwen_base.DEFAULT_SPLIT, qwen_base.DEFAULT_RULE_RESULTS]
    before = {str(path): baseline.sha256_file(path) for path in protected}
    qwen_base.assert_protected_unchanged(before)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fit, validation, boundary, rule_by_id = load_partitions()
    support = label_support(fit)
    baseline.write_json(args.output_dir / "discriminative_label_support_v1.json", support)
    split = internal_split(fit)
    baseline.write_json(args.output_dir / "discriminative_internal_split_v1.json", split)

    if not args.model_dir.is_dir():
        raise RuntimeError("BGE_M3_AVAILABILITY_GATE_BLOCKED")
    provider = BgeM3EmbeddingProvider(BgeM3EmbeddingProviderConfig(model_dir=args.model_dir, device=args.device, batch_size=16, normalize=True, max_length=512))
    if not provider.health_check()["available"]:
        raise RuntimeError("BGE_M3_AVAILABILITY_GATE_BLOCKED")
    if args.device == "cuda" and not torch.cuda.is_available():
        args.device = "cpu"
        provider = BgeM3EmbeddingProvider(BgeM3EmbeddingProviderConfig(model_dir=args.model_dir, device="cpu", batch_size=16, normalize=True, max_length=512))
    torch.cuda.empty_cache() if torch.cuda.is_available() else None
    torch.cuda.reset_peak_memory_stats() if args.device == "cuda" else None
    provider.encoder._load()
    for parameter in provider.encoder.model.parameters():
        parameter.requires_grad_(False)
    trainable_parameter_tensors = sum(parameter.requires_grad for parameter in provider.encoder.model.parameters())
    if trainable_parameter_tensors:
        raise RuntimeError("BGE_M3_NOT_FROZEN")
    model_hash = provider.model_hash().upper()
    all_cases = fit + validation + boundary
    vectors, cache_manifest = cache_embeddings(provider, all_cases, args.output_dir, model_hash)
    baseline.write_json(args.output_dir / "bge_m3_embedding_cache_manifest_v1.json", cache_manifest)
    by_id = {case["caseId"]: index for index, case in enumerate(all_cases)}
    split_by_id = {row["caseId"]: row["partition"] for row in split["rows"]}
    train_cases = [case for case in fit if split_by_id[case["caseId"]] == "TRAIN"]
    dev_cases = [case for case in fit if split_by_id[case["caseId"]] == "DEV"]
    train_vectors = np.stack([vectors[by_id[case["caseId"]]] for case in train_cases])
    dev_vectors = np.stack([vectors[by_id[case["caseId"]]] for case in dev_cases])
    threshold_value, threshold_artifact = select_threshold(train_vectors, train_cases, dev_vectors, dev_cases)
    threshold_artifact["internalSplitHash"] = split["splitHash"]
    baseline.write_json(args.output_dir / "discriminative_threshold_selection_v1.json", threshold_artifact)

    fit_vectors = np.stack([vectors[by_id[case["caseId"]]] for case in fit])
    training_started = time.perf_counter_ns()
    model, head_status = fit_heads(fit_vectors, multilabel_encode(fit))
    final_training_ms = round((time.perf_counter_ns() - training_started) / 1_000_000, 3)
    artifact = {**model, "globalThreshold": threshold_value, "benchmarkVersion": BENCHMARK_VERSION}
    model_path = args.output_dir / "bge_m3_logistic_router_v1.joblib"
    joblib.dump(artifact, model_path, compress=3)
    model_artifact_sha = baseline.sha256_file(model_path)

    validation_vectors = np.stack([vectors[by_id[case["caseId"]]] for case in validation])
    boundary_vectors = np.stack([vectors[by_id[case["caseId"]]] for case in boundary])
    validation_rows = evaluate_cases(validation, predict_scores(model, validation_vectors), threshold_value)
    boundary_rows = evaluate_cases(boundary, predict_scores(model, boundary_vectors), threshold_value)
    baseline.write_jsonl(args.output_dir / "bge_logistic_validation_outputs_v1.jsonl", validation_rows)
    baseline.write_jsonl(args.output_dir / "bge_logistic_boundary_outputs_v1.jsonl", boundary_rows)
    trainable_labels = [item["riskType"] for item in head_status if item["status"] == "TRAINED"]
    quality = quality_metrics(validation_rows, boundary_rows, trainable_labels)
    safety = safety_metrics(validation_rows + boundary_rows)

    rule_validation_rows = [rule_by_id[case["caseId"]] for case in validation]
    rule_boundary_rows = [rule_by_id[case["caseId"]] for case in boundary]
    rule_validation = qwen_base.rule_baseline(rule_validation_rows)
    rule_boundary = qwen_base.rule_baseline(rule_boundary_rows)
    rule_combined = qwen_base.rule_baseline(rule_validation_rows + rule_boundary_rows)
    comparison = comparison_artifact(rule_validation, rule_boundary, rule_combined, quality, safety)
    baseline.write_json(args.output_dir / "rule_vs_bge_logistic_comparison_v1.json", comparison)

    evaluation_by_id = {row["caseId"]: row for row in validation_rows + boundary_rows}
    diagnostic_ids = list(gpu_qwen.CHECKPOINT_CASE_IDS)
    diagnostic_bge_rows = [evaluation_by_id[case_id] for case_id in diagnostic_ids]
    diagnostic_bge = multilabel_metrics(diagnostic_bge_rows)
    diagnostic_bge_safety = safety_metrics(diagnostic_bge_rows)
    qwen_metrics = json.loads((gpu_qwen.DEFAULT_OUTPUT_DIR / "gpu_20case_checkpoint_metrics_v1.json").read_text(encoding="utf-8"))
    diagnostic = {
        "schemaVersion": "diagnostic-20case-three-way-comparison-v1",
        "scope": "DIAGNOSTIC_20_CASE_ONLY",
        "caseIds": diagnostic_ids,
        "rule": {"exactSetMatchAccuracy": qwen_metrics["rule"]["exactSetMatchAccuracy"], "microF1": qwen_metrics["rule"]["microF1"], "materialSafetyErrorCount": qwen_metrics["rule"]["materialSafetyErrorCount"]},
        "qwen3_1_7b": {"exactSetMatchAccuracy": qwen_metrics["qwen"]["exactSetMatchAccuracy"], "microF1": qwen_metrics["qwen"]["microF1"], "materialSafetyErrorCount": qwen_metrics["qwen"]["materialSafetyErrorCount"]},
        "bgeM3Logistic": {"exactSetMatchAccuracy": diagnostic_bge["exactSetMatchAccuracy"], "microF1": diagnostic_bge["microF1"], "materialSafetyErrorCount": diagnostic_bge_safety["materialSafetyErrorCount"]},
    }
    baseline.write_json(args.output_dir / "diagnostic_20case_three_way_comparison_v1.json", diagnostic)

    latency = latency_metrics(provider, model, validation + boundary, threshold_value)
    quality["latency"] = latency
    reliability = reliability_diagnostic(validation_rows + boundary_rows, threshold_value)
    quality["reliabilityDiagnostic"] = reliability
    baseline.write_json(args.output_dir / "bge_logistic_quality_metrics_v1.json", quality)
    baseline.write_json(args.output_dir / "bge_logistic_safety_metrics_v1.json", safety)

    encoder_parameter = next(provider.encoder.model.parameters())
    metadata = provider.metadata()
    manifest = {
        "schemaVersion": "bge-m3-logistic-model-manifest-v1",
        "benchmarkVersion": BENCHMARK_VERSION,
        "embeddingModelId": MODEL_ID,
        "embeddingModelRevision": model_hash,
        "embeddingImplementation": "project-existing-transformers-cls-l2",
        "embeddingDimension": int(vectors.shape[1]),
        "device": str(encoder_parameter.device),
        "dtype": str(encoder_parameter.dtype).replace("torch.", ""),
        "normalized": True,
        "encoderFrozen": True,
        "trainableEncoderParameterTensors": trainable_parameter_tensors,
        "peakAllocatedVramMiB": round(torch.cuda.max_memory_allocated() / 1048576, 2) if args.device == "cuda" else 0,
        "peakReservedVramMiB": round(torch.cuda.max_memory_reserved() / 1048576, 2) if args.device == "cuda" else 0,
        "labels": list(LABELS),
        "headStatus": head_status,
        "logisticParameters": LR_PARAMETERS,
        "globalThreshold": threshold_value,
        "trainingPartition": "CALIBRATION_FIT_80_ONLY",
        "thresholdSelectionPartition": "FIT_INTERNAL_TRAIN_64_DEV_16",
        "trainingDatasetHash": baseline.sha256_file(qwen_base.DEFAULT_CALIBRATION),
        "trainingSplitHash": split["splitHash"],
        "modelArtifactSha": model_artifact_sha,
        "embeddingExtractionTimeMs": cache_manifest["embeddingExtractionTimeMs"],
        "finalTrainingTimeMs": final_training_ms,
        "externalApiCallCount": 0,
        "frozenBenchmarkExecuted": False,
        "providerMetadata": {key: value for key, value in metadata.items() if key not in {"model_path_label"}},
    }
    baseline.write_json(args.output_dir / "bge_m3_logistic_model_manifest_v1.json", manifest)

    material_reduction = comparison["gains"]["materialSafetyErrorReduction"]
    clearly_safer = material_reduction >= max(2, math.ceil(rule_combined["materialSafetyErrorCount"] * 0.10))
    validation_f1 = quality["validation"]["microF1"]
    boundary_f1 = quality["boundary"]["overall"]["microF1"]
    multi_f1 = quality["slices"]["multiRisk"]["microF1"]
    candidate_pass = validation_f1 >= 0.65 and boundary_f1 >= 0.55 and multi_f1 >= 0.55 and clearly_safer
    candidate_limited = validation_f1 >= 0.50 and comparison["gains"]["validationMicroF1"] >= 0.05 and safety["materialSafetyErrorCount"] <= rule_combined["materialSafetyErrorCount"]
    candidate_gate = "PASS" if candidate_pass else "PASS_WITH_LIMITATIONS" if candidate_limited else "FAIL"
    if candidate_gate == "PASS":
        recommendation = "DISCRIMINATIVE_ROUTER_PROMISING"
    elif candidate_gate == "PASS_WITH_LIMITATIONS" or comparison["gains"]["validationMicroF1"] >= 0.05:
        recommendation = "EXPAND_TRAINING_DATA_BEFORE_ROUTER"
    else:
        recommendation = "LINEAR_EMBEDDING_ROUTER_INSUFFICIENT"
    gate = {
        "bgeM3AvailabilityGate": "PASS",
        "labelSupportGate": support["gate"],
        "embeddingGate": "PASS",
        "logisticTrainGate": "PASS",
        "thresholdSelectionGate": threshold_artifact["gate"],
        "validationGate": "PASS",
        "boundaryGate": "PASS",
        "safetyEvaluationGate": "PASS",
        "step21_3a_2Gate": "PASS",
        "discriminativeRouterCandidateGate": candidate_gate,
        "calibrationSha": baseline.sha256_file(qwen_base.DEFAULT_CALIBRATION),
        "boundarySha": baseline.sha256_file(qwen_base.DEFAULT_BOUNDARY),
        "frozenGoldSha": baseline.sha256_file(qwen_base.DEFAULT_FROZEN),
        "frozenBenchmarkExecuted": False,
        "externalApiCallCount": 0,
        "nextRecommendation": recommendation,
    }
    baseline.write_json(args.output_dir / "step213a2_discriminative_gate_v1.json", gate)
    args.report.write_text(build_report(manifest, support, threshold_artifact, quality, comparison, diagnostic, latency, gate), encoding="utf-8", newline="\n")
    provider.close()
    qwen_base.assert_protected_unchanged(before)
    return {"manifest": manifest, "support": support, "threshold": threshold_artifact, "quality": quality, "safety": safety, "comparison": comparison, "diagnostic": diagnostic, "latency": latency, "gate": gate}


def main() -> int:
    result = run(parse_args())
    print(json.dumps({"gate": result["gate"], "quality": result["quality"], "diagnostic": result["diagnostic"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
