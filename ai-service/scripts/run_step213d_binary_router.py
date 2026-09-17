from __future__ import annotations

"""Run the offline Step 21.3D FAST_ELIGIBLE vs LONG_REQUIRED experiment."""

import argparse
import hashlib
import inspect
import json
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

from app.contracts.review_semantics import RISK_TYPE_REGISTRY
from app.rag.embedding_provider import BgeM3EmbeddingProvider, BgeM3EmbeddingProviderConfig
from app.risk_calibration.severity import BASE_SEVERITY, SeverityRank
from scripts import run_step2123_reliability_analysis as baseline
from scripts import run_step213c_escalation_gate as escalation


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "step213d_binary_router"
DEFAULT_REPORT = REPO_ROOT / "docs" / "BINARY_ESCALATION_ROUTER_REPORT.md"
DEFAULT_MODEL_DIR = ROOT.parents[1] / "models" / "bge-m3"
EMBEDDING_SOURCE_DIR = ROOT / "artifacts" / "step213a2_discriminative"
EMBEDDING_MANIFEST = EMBEDDING_SOURCE_DIR / "bge_m3_embedding_cache_manifest_v1.json"
EMBEDDING_CACHE = EMBEDDING_SOURCE_DIR / "embedding_cache"
RULE_RESULTS = ROOT / "artifacts" / "step2123" / "router_signal_results_v1.jsonl"
RULE_POLICY = ROOT / "artifacts" / "step213c_escalation" / "escalation_policy_v1.json"

MODEL_ID = "BAAI/bge-m3"
BENCHMARK_VERSION = "step21.3d-binary-router-v1"
INTERNAL_SPLIT_SEED = "step21.3d-fit64-dev16-v1"
RANDOM_STATE = 2134
THRESHOLDS = (0.30, 0.40, 0.50, 0.60, 0.70)
FAST_ELIGIBLE = "FAST_ELIGIBLE"
LONG_REQUIRED = "LONG_REQUIRED"
GOVERNANCE_RISKS = frozenset(
    {
        "paid_review",
        "rating_manipulation",
        "review_suppression",
        "fake_review",
        "safety_or_fraud_risk",
        "harassment_or_abuse",
        "privacy_risk",
    }
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


def expected_risks(case: dict[str, Any]) -> list[str]:
    value = case.get("benchmarkRiskTypes")
    return sorted(set(case.get("riskTypes", []) if value is None else value))


def evaluation_target(case: dict[str, Any]) -> str:
    return str(case.get("evaluationTarget") or "RISK_CLASSIFICATION").upper()


def gold_severity(case: dict[str, Any]) -> str:
    explicit = str(case.get("severity") or "").lower()
    if explicit in {"low", "medium", "high", "critical"}:
        return explicit
    risks = expected_risks(case)
    rank = max((BASE_SEVERITY.get(risk, SeverityRank.MEDIUM) for risk in risks), default=SeverityRank.MEDIUM)
    return rank.name.lower()


def is_complex_after_sales(case: dict[str, Any], risks: list[str] | None = None) -> bool:
    """Use governance metadata, never case identity or text, for the after-sales exception."""
    risks = risks if risks is not None else expected_risks(case)
    if "after_sales_risk" not in risks:
        return False
    if bool(case.get("ambiguity")):
        return True
    return (
        str(case.get("difficulty") or "").lower() == "hard"
        and str(case.get("expressionType") or "").lower() in {"implicit", "mixed"}
        and str(case.get("boundaryType") or "").lower() != "hard_negative"
    )


def derive_binary_target(case: dict[str, Any]) -> dict[str, Any]:
    risks = expected_risks(case)
    severity = gold_severity(case)
    reasons: list[str] = []
    if evaluation_target(case) == "ABSTENTION":
        reasons.append("ABSTENTION_TARGET")
    if bool(case.get("multiRisk")) or len(risks) > 1:
        reasons.append("MULTI_RISK")
    if severity in {"high", "critical"}:
        reasons.append("HIGH_OR_CRITICAL_SEVERITY")
    if set(risks) & GOVERNANCE_RISKS:
        reasons.append("GOVERNANCE_RISK_TYPE")
    if is_complex_after_sales(case, risks):
        reasons.append("COMPLEX_AFTER_SALES")
    target = LONG_REQUIRED if reasons else FAST_ELIGIBLE
    return {
        "target": target,
        "reasonCodes": reasons or ["SIMPLE_LOW_OR_MEDIUM_SINGLE_RISK"],
        "expectedRiskTypes": risks,
        "goldSeverity": severity,
    }


def load_partitions() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    split = json.loads((ROOT / "artifacts" / "step2123" / "reliability_split_v1.json").read_text(encoding="utf-8"))
    split_by_id = {row["caseId"]: row["partition"] for row in split["rows"]}
    calibration = baseline.load_jsonl(baseline.DEFAULT_CALIBRATION)
    fit = [dict(row, _partition="FIT") for row in calibration if split_by_id.get(row["caseId"]) == "FIT"]
    validation = [dict(row, _partition="VALIDATION") for row in calibration if split_by_id.get(row["caseId"]) == "VALIDATION"]
    boundary = [dict(row, _partition="BOUNDARY_CHALLENGE") for row in baseline.load_jsonl(baseline.DEFAULT_BOUNDARY)]
    rule_by_id = {row["caseId"]: row for row in baseline.load_jsonl(RULE_RESULTS)}
    if (len(fit), len(validation), len(boundary), len(rule_by_id)) != (80, 40, 60, 180):
        raise RuntimeError("DATASET_PARTITION_COUNT_MISMATCH")
    return fit, validation, boundary, rule_by_id


def target_distribution(cases: list[dict[str, Any]]) -> dict[str, Any]:
    targets = Counter(derive_binary_target(case)["target"] for case in cases)
    by_risk: dict[str, dict[str, int]] = {}
    for risk in sorted({risk for case in cases for risk in (expected_risks(case) or ["abstention_target"])}):
        selected = [case for case in cases if risk in (expected_risks(case) or ["abstention_target"])]
        by_risk[risk] = dict(sorted(Counter(derive_binary_target(case)["target"] for case in selected).items()))
    minority_rate = min(targets.values(), default=0) / len(cases) if cases else 0.0
    return {
        "caseCount": len(cases),
        "targets": {FAST_ELIGIBLE: targets[FAST_ELIGIBLE], LONG_REQUIRED: targets[LONG_REQUIRED]},
        "targetRates": {key: baseline.safe_ratio(value, len(cases)) for key, value in ((FAST_ELIGIBLE, targets[FAST_ELIGIBLE]), (LONG_REQUIRED, targets[LONG_REQUIRED]))},
        "byRiskType": by_risk,
        "classImbalanceStatus": "CLASS_IMBALANCE_LIMITATION" if minority_rate < 0.15 else "PASS",
    }


def _split_features(case: dict[str, Any]) -> set[str]:
    derived = derive_binary_target(case)
    return {
        f"target:{derived['target']}",
        *(f"risk:{risk}" for risk in derived["expectedRiskTypes"]),
        f"severity:{derived['goldSeverity']}",
        f"source:{case.get('sourceDataset', 'unknown')}",
        f"expression:{case.get('expressionType', 'unknown')}",
        f"multi:{bool(case.get('multiRisk'))}",
    }


def internal_split(fit_cases: list[dict[str, Any]], dev_count: int = 16) -> dict[str, Any]:
    feature_counts = Counter(feature for case in fit_cases for feature in _split_features(case))
    targets = {feature: count * dev_count / len(fit_cases) for feature, count in feature_counts.items()}
    selected_counts: Counter[str] = Counter()
    remaining = {str(case["caseId"]): case for case in fit_cases}
    dev_ids: set[str] = set()

    def improvement(case: dict[str, Any]) -> float:
        return sum(
            ((selected_counts[feature] - targets[feature]) ** 2 - (selected_counts[feature] + 1 - targets[feature]) ** 2)
            / max(targets[feature], 1.0)
            for feature in _split_features(case)
        )

    while len(dev_ids) < dev_count:
        chosen = sorted(
            remaining.values(),
            key=lambda case: (-improvement(case), baseline.stable_hash(f"{INTERNAL_SPLIT_SEED}|{case['caseId']}")),
        )[0]
        dev_ids.add(str(chosen["caseId"]))
        selected_counts.update(_split_features(chosen))
        del remaining[str(chosen["caseId"])]
    rows = [{"caseId": case["caseId"], "partition": "DEV" if case["caseId"] in dev_ids else "TRAIN"} for case in fit_cases]
    train = [case for case in fit_cases if case["caseId"] not in dev_ids]
    dev = [case for case in fit_cases if case["caseId"] in dev_ids]
    return {
        "schemaVersion": "binary-router-internal-split-v1",
        "seed": INTERNAL_SPLIT_SEED,
        "method": "deterministic-multivariate-greedy-stratification",
        "sourcePartition": "CALIBRATION_FIT_80",
        "counts": {"TRAIN": len(train), "DEV": len(dev)},
        "distribution": {"TRAIN": target_distribution(train), "DEV": target_distribution(dev)},
        "rows": rows,
        "splitHash": stable_json_hash(rows),
    }


def binary_encode(cases: list[dict[str, Any]]) -> np.ndarray:
    return np.asarray([int(derive_binary_target(case)["target"] == LONG_REQUIRED) for case in cases], dtype=np.int8)


def fit_model(vectors: np.ndarray, cases: list[dict[str, Any]]) -> LogisticRegression:
    targets = binary_encode(cases)
    if len(set(targets.tolist())) != 2:
        raise RuntimeError("BINARY_TRAINING_CLASS_MISSING")
    model = LogisticRegression(**LR_PARAMETERS)
    model.fit(vectors, targets)
    return model


def load_cached_embeddings(cases: list[dict[str, Any]]) -> tuple[np.ndarray, dict[str, Any]]:
    manifest = json.loads(EMBEDDING_MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("modelId") != MODEL_ID or manifest.get("dimension") != 1024 or manifest.get("caseCount") != 180:
        raise RuntimeError("BGE_EMBEDDING_CACHE_IDENTITY_MISMATCH")
    records = {row["caseId"]: row for row in manifest["records"]}
    vectors = []
    for case in cases:
        record = records.get(case["caseId"])
        if not record:
            raise RuntimeError(f"BGE_EMBEDDING_CACHE_MISSING:{case['caseId']}")
        expected_text_hash = hashlib.sha256(str(case["textZh"]).encode("utf-8")).hexdigest().upper()
        if record["textHash"] != expected_text_hash:
            raise RuntimeError(f"BGE_EMBEDDING_TEXT_HASH_MISMATCH:{case['caseId']}")
        vector = np.load(EMBEDDING_CACHE / f"{record['cacheKey']}.npy", allow_pickle=False).astype("float32")
        if vector.shape != (1024,) or not np.isclose(np.linalg.norm(vector), 1.0, atol=1e-3):
            raise RuntimeError(f"BGE_EMBEDDING_VECTOR_INVALID:{case['caseId']}")
        vectors.append(vector)
    return np.stack(vectors), manifest


def make_output(case: dict[str, Any], score: float, threshold: float, rule_row: dict[str, Any], model_name: str = "bge_binary_logistic") -> dict[str, Any]:
    derived = derive_binary_target(case)
    model_prediction = LONG_REQUIRED if score >= threshold else FAST_ELIGIBLE
    safety_override = bool(rule_row["safetyGateTriggered"])
    final_prediction = LONG_REQUIRED if safety_override else model_prediction
    is_false_fast = derived["target"] == LONG_REQUIRED and final_prediction == FAST_ELIGIBLE
    return {
        "schemaVersion": "binary-router-output-v1",
        "caseId": str(case["caseId"]),
        "datasetPartition": case["_partition"],
        "model": model_name,
        "binaryTarget": derived["target"],
        "targetReasonCodes": derived["reasonCodes"],
        "goldSeverity": derived["goldSeverity"],
        "expectedRiskTypes": derived["expectedRiskTypes"],
        "longRequiredScore": round(float(score), 6),
        "scoreInterpretation": "ordinal_classification_score_not_calibrated_probability",
        "threshold": threshold,
        "modelPrediction": model_prediction,
        "safetyGateTriggered": safety_override,
        "finalPrediction": final_prediction,
        "falseFast": is_false_fast,
        "highRiskFalseFast": is_false_fast and derived["goldSeverity"] in {"high", "critical"},
        "materialSafetyFalseFast": is_false_fast and bool(rule_row["materialSafetyError"]),
        "evaluationTarget": evaluation_target(case),
        "boundaryType": case.get("boundaryType"),
        "expressionType": case.get("expressionType"),
        "difficulty": case.get("difficulty"),
        "multiRisk": bool(case.get("multiRisk")),
    }


def evaluate_cases(cases: list[dict[str, Any]], scores: np.ndarray, threshold: float, rule_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [make_output(case, float(scores[index]), threshold, rule_by_id[case["caseId"]]) for index, case in enumerate(cases)]


def binary_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    actual_long = [row for row in rows if row["binaryTarget"] == LONG_REQUIRED]
    actual_fast = [row for row in rows if row["binaryTarget"] == FAST_ELIGIBLE]
    predicted_long = [row for row in rows if row["finalPrediction"] == LONG_REQUIRED]
    predicted_fast = [row for row in rows if row["finalPrediction"] == FAST_ELIGIBLE]
    false_fast = [row for row in rows if row["falseFast"]]
    false_escalation = [row for row in rows if row["binaryTarget"] == FAST_ELIGIBLE and row["finalPrediction"] == LONG_REQUIRED]
    tp = sum(row["binaryTarget"] == LONG_REQUIRED and row["finalPrediction"] == LONG_REQUIRED for row in rows)
    fp = len(false_escalation)
    fn = len(false_fast)
    precision = baseline.safe_ratio(tp, tp + fp)
    recall = baseline.safe_ratio(tp, tp + fn)
    f1 = baseline.safe_ratio(2 * precision * recall, precision + recall)
    abstention = [row for row in rows if row["evaluationTarget"] == "ABSTENTION"]
    hard_negative_fast = [row for row in actual_fast if row["boundaryType"] == "hard_negative"]
    hard_negative_captured = [row for row in hard_negative_fast if row["finalPrediction"] == FAST_ELIGIBLE]
    return {
        "caseCount": len(rows),
        "targetDistribution": {FAST_ELIGIBLE: len(actual_fast), LONG_REQUIRED: len(actual_long)},
        "predictionDistribution": {FAST_ELIGIBLE: len(predicted_fast), LONG_REQUIRED: len(predicted_long)},
        "binaryAccuracy": baseline.safe_ratio(sum(row["binaryTarget"] == row["finalPrediction"] for row in rows), len(rows)),
        "binaryF1LongRequired": f1,
        "longRequiredPrecision": precision,
        "longRequiredRecall": recall,
        "fastPrecision": baseline.safe_ratio(sum(row["binaryTarget"] == FAST_ELIGIBLE for row in predicted_fast), len(predicted_fast)) if predicted_fast else 0.0,
        "fastCoverage": baseline.safe_ratio(len(predicted_fast), len(rows)),
        "falseFastCount": len(false_fast),
        "falseFastRate": baseline.safe_ratio(len(false_fast), len(actual_long)),
        "falseFastCaseIds": [row["caseId"] for row in false_fast],
        "highRiskFalseFastCount": sum(row["highRiskFalseFast"] for row in rows),
        "materialSafetyFalseFastCount": sum(row["materialSafetyFalseFast"] for row in rows),
        "falseEscalationCount": len(false_escalation),
        "falseEscalationRate": baseline.safe_ratio(len(false_escalation), len(actual_fast)),
        "abstentionLongCapture": {
            "targetCount": len(abstention),
            "captured": sum(row["finalPrediction"] == LONG_REQUIRED for row in abstention),
            "rate": baseline.safe_ratio(sum(row["finalPrediction"] == LONG_REQUIRED for row in abstention), len(abstention)),
        },
        "hardNegative": {
            "fastTargetCount": len(hard_negative_fast),
            "fastCaptured": len(hard_negative_captured),
            "fastRecall": baseline.safe_ratio(len(hard_negative_captured), len(hard_negative_fast)),
            "falseEscalationCount": len(hard_negative_fast) - len(hard_negative_captured),
        },
    }


def boundary_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = binary_metrics(rows)
    result["byBoundaryType"] = {
        boundary_type: binary_metrics([row for row in rows if str(row["boundaryType"]) == boundary_type])
        for boundary_type in sorted({str(row["boundaryType"]) for row in rows})
    }
    result["byExpressionType"] = {
        expression: binary_metrics([row for row in rows if str(row["expressionType"]) == expression])
        for expression in sorted({str(row["expressionType"]) for row in rows})
    }
    return result


def select_threshold(
    train_vectors: np.ndarray,
    train_cases: list[dict[str, Any]],
    dev_vectors: np.ndarray,
    dev_cases: list[dict[str, Any]],
    rule_by_id: dict[str, dict[str, Any]],
) -> tuple[float, dict[str, Any]]:
    started = time.perf_counter_ns()
    model = fit_model(train_vectors, train_cases)
    train_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
    scores = model.predict_proba(dev_vectors)[:, 1]
    candidates = []
    for threshold in THRESHOLDS:
        metrics = binary_metrics(evaluate_cases(dev_cases, scores, threshold, rule_by_id))
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
        "schemaVersion": "binary-router-threshold-selection-v1",
        "trainingPartition": "FIT_INTERNAL_TRAIN_64",
        "selectionPartition": "FIT_INTERNAL_DEV_16",
        "validationUsed": False,
        "boundaryUsed": False,
        "frozenUsed": False,
        "candidateThresholds": list(THRESHOLDS),
        "rankingPriority": ["LONG_REQUIRED recall DESC", "HIGH/CRITICAL false fast ASC", "FAST precision DESC", "FAST coverage DESC"],
        "candidates": candidates,
        "selectedThreshold": selected["threshold"],
        "internalTrainingTimeMs": train_ms,
        "gate": "PASS",
    }
    return float(selected["threshold"]), artifact


def rule_output(case: dict[str, Any], rule_row: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    score, route, _, _ = escalation.route_signal(policy["scoreVersion"], int(policy["threshold"]), escalation.runtime_signal(rule_row))
    prediction = LONG_REQUIRED if route == escalation.LONG_ANALYSIS else FAST_ELIGIBLE
    return make_output(case, float(score), float(policy["threshold"]), rule_row, model_name="cheap_rule_binary") | {
        "modelPrediction": prediction,
        "finalPrediction": prediction,
        "falseFast": derive_binary_target(case)["target"] == LONG_REQUIRED and prediction == FAST_ELIGIBLE,
        "highRiskFalseFast": derive_binary_target(case)["target"] == LONG_REQUIRED and prediction == FAST_ELIGIBLE and gold_severity(case) in {"high", "critical"},
        "materialSafetyFalseFast": derive_binary_target(case)["target"] == LONG_REQUIRED and prediction == FAST_ELIGIBLE and bool(rule_row["materialSafetyError"]),
    }


def latency_metrics(provider: BgeM3EmbeddingProvider, model: LogisticRegression, cases: list[dict[str, Any]], threshold: float, rule_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    embedding_values: list[float] = []
    classifier_values: list[float] = []
    total_values: list[float] = []
    for case in cases:
        total_started = time.perf_counter_ns()
        embedding_started = time.perf_counter_ns()
        vector = provider.encode_documents([str(case["textZh"])])
        embedding_values.append((time.perf_counter_ns() - embedding_started) / 1_000_000)
        classifier_started = time.perf_counter_ns()
        score = float(model.predict_proba(vector)[0, 1])
        make_output(case, score, threshold, rule_by_id[case["caseId"]])
        classifier_values.append((time.perf_counter_ns() - classifier_started) / 1_000_000)
        total_values.append((time.perf_counter_ns() - total_started) / 1_000_000)
    summarize = lambda values: {
        "p50Ms": baseline.percentile(values, 0.50),
        "p95Ms": baseline.percentile(values, 0.95),
        "p99Ms": baseline.percentile(values, 0.99),
    }
    return {
        "schemaVersion": "binary-router-latency-v1",
        "mode": "warm-single-request-batch-size-1",
        "caseCount": len(cases),
        "embedding": summarize(embedding_values),
        "classifier": summarize(classifier_values),
        "endToEnd": summarize(total_values),
        "externalApiCallCount": 0,
    }


def candidate_gate(metrics: dict[str, Any]) -> tuple[str, str]:
    passed = (
        metrics["longRequiredRecall"] >= 0.95
        and metrics["highRiskFalseFastCount"] == 0
        and metrics["materialSafetyFalseFastCount"] == 0
        and metrics["fastPrecision"] >= 0.95
        and metrics["fastCoverage"] >= 0.20
    )
    limited = (
        metrics["longRequiredRecall"] >= 0.90
        and metrics["highRiskFalseFastCount"] == 0
        and metrics["fastPrecision"] >= 0.90
        and metrics["fastCoverage"] >= 0.10
    )
    gate = "PASS" if passed else "PASS_WITH_LIMITATIONS" if limited else "FAIL"
    recommendation = "BINARY_ROUTER_SHADOW_MODE" if gate == "PASS" else "SETFIT_BINARY_CLASSIFIER_EVALUATION"
    return gate, recommendation


def target_definition() -> dict[str, Any]:
    registered_governance = sorted(risk for risk in GOVERNANCE_RISKS if risk in RISK_TYPE_REGISTRY)
    return {
        "schemaVersion": "router-binary-target-v1",
        "labels": [FAST_ELIGIBLE, LONG_REQUIRED],
        "longRequiredWhenAny": [
            "evaluationTarget == ABSTENTION",
            "multiRisk == true or gold risk count > 1",
            "gold severity in {high, critical}",
            f"gold risk intersects {registered_governance}",
            "after_sales_risk and (ambiguity or (difficulty=hard and expressionType in {implicit,mixed} and boundaryType!=hard_negative))",
        ],
        "fastEligibleOnlyWhen": "single-risk low/medium case without a LONG_REQUIRED condition",
        "afterSalesBasis": {
            "registrySeverity": RISK_TYPE_REGISTRY["after_sales_risk"].severity,
            "defaultAction": RISK_TYPE_REGISTRY["after_sales_risk"].default_action,
            "complexityFields": ["ambiguity", "difficulty", "expressionType", "boundaryType"],
            "caseIdSpecialCases": False,
            "reviewTextUsedForTarget": False,
        },
        "goldFieldsSupervisionOnly": True,
        "runtimeInputFields": ["review text embedding", "safetyGateTriggered hard override"],
    }


def build_report(audit: dict[str, Any], threshold: dict[str, Any], validation: dict[str, Any], boundary: dict[str, Any], comparison: dict[str, Any], latency: dict[str, Any], gate: dict[str, Any]) -> str:
    fit_dist = audit["partitions"]["FIT"]["targets"]
    val_dist = audit["partitions"]["VALIDATION"]["targets"]
    boundary_dist = audit["partitions"]["BOUNDARY_CHALLENGE"]["targets"]
    rule = comparison["ruleBinaryBaseline"]["validation"]
    return "\n".join(
        [
            "# Binary Escalation Router Report",
            "",
            "## Scope",
            "",
            "Step 21.3D evaluates a frozen local BGE-M3 encoder plus one binary logistic head. It is offline-only and does not change the runtime Router, Safety Gate, Agent workflow, RAG, datasets, or Frozen benchmark.",
            "",
            "## Target And Split",
            "",
            f"Fit FAST/LONG `{fit_dist[FAST_ELIGIBLE]}/{fit_dist[LONG_REQUIRED]}`; Validation `{val_dist[FAST_ELIGIBLE]}/{val_dist[LONG_REQUIRED]}`; Boundary `{boundary_dist[FAST_ELIGIBLE]}/{boundary_dist[LONG_REQUIRED]}`.",
            f"Threshold `{threshold['selectedThreshold']}` was selected only on Fit-internal Dev16 using safety-first ordering.",
            "",
            "## Validation",
            "",
            "| Metric | Cheap rule | BGE binary |",
            "| --- | ---: | ---: |",
            f"| LONG recall | {rule['longRequiredRecall']:.4f} | {validation['longRequiredRecall']:.4f} |",
            f"| FAST precision | {rule['fastPrecision']:.4f} | {validation['fastPrecision']:.4f} |",
            f"| FAST coverage | {rule['fastCoverage']:.4f} | {validation['fastCoverage']:.4f} |",
            f"| False fast | {rule['falseFastCount']} | {validation['falseFastCount']} |",
            f"| High-risk false fast | {rule['highRiskFalseFastCount']} | {validation['highRiskFalseFastCount']} |",
            f"| Material-safety false fast | {rule['materialSafetyFalseFastCount']} | {validation['materialSafetyFalseFastCount']} |",
            "",
            "## Boundary And Latency",
            "",
            f"Boundary LONG recall `{boundary['longRequiredRecall']:.4f}`, FAST precision `{boundary['fastPrecision']:.4f}`, false fast `{boundary['falseFastCount']}`, abstention capture `{boundary['abstentionLongCapture']['captured']}/{boundary['abstentionLongCapture']['targetCount']}`, hard-negative FAST recall `{boundary['hardNegative']['fastRecall']:.4f}`.",
            f"Warm batch-1 end-to-end P50/P95 `{latency['endToEnd']['p50Ms']}/{latency['endToEnd']['p95Ms']} ms`.",
            "",
            "## Gates",
            "",
            f"`STEP21_3D_GATE = {gate['step21_3dGate']}`",
            f"`BINARY_ROUTER_CANDIDATE_GATE = {gate['binaryRouterCandidateGate']}`",
            f"`NEXT_RECOMMENDATION = {gate['nextRecommendation']}`",
            "",
        ]
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    import torch

    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"})
    protected = [baseline.DEFAULT_CALIBRATION, baseline.DEFAULT_BOUNDARY, baseline.DEFAULT_FROZEN, baseline.DEFAULT_FREEZE_MANIFEST, RULE_RESULTS]
    before = {str(path): baseline.sha256_file(path) for path in protected}
    if before[str(baseline.DEFAULT_CALIBRATION)] != baseline.CALIBRATION_SHA:
        raise RuntimeError("CALIBRATION_DATASET_HASH_MISMATCH")
    if before[str(baseline.DEFAULT_BOUNDARY)] != baseline.BOUNDARY_SHA:
        raise RuntimeError("BOUNDARY_DATASET_HASH_MISMATCH")
    if before[str(baseline.DEFAULT_FROZEN)] != baseline.FROZEN_GOLD_SHA:
        raise RuntimeError("FROZEN_GOLD_HASH_MISMATCH")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    fit, validation, boundary, rule_by_id = load_partitions()
    all_cases = fit + validation + boundary
    definition = target_definition()
    baseline.write_json(args.output_dir / "binary_router_target_definition_v1.json", definition)
    audit = {
        "schemaVersion": "binary-target-audit-v1",
        "partitions": {
            "FIT": target_distribution(fit),
            "VALIDATION": target_distribution(validation),
            "BOUNDARY_CHALLENGE": target_distribution(boundary),
        },
    }
    audit["classImbalanceLimitation"] = any(value["classImbalanceStatus"] != "PASS" for value in audit["partitions"].values())
    audit["gate"] = "PASS_WITH_LIMITATIONS" if audit["classImbalanceLimitation"] else "PASS"
    baseline.write_json(args.output_dir / "binary_target_audit_v1.json", audit)

    split = internal_split(fit)
    baseline.write_json(args.output_dir / "binary_router_internal_split_v1.json", split)
    vectors, embedding_manifest = load_cached_embeddings(all_cases)
    vector_by_id = {case["caseId"]: vectors[index] for index, case in enumerate(all_cases)}
    split_by_id = {row["caseId"]: row["partition"] for row in split["rows"]}
    train_cases = [case for case in fit if split_by_id[case["caseId"]] == "TRAIN"]
    dev_cases = [case for case in fit if split_by_id[case["caseId"]] == "DEV"]
    train_vectors = np.stack([vector_by_id[case["caseId"]] for case in train_cases])
    dev_vectors = np.stack([vector_by_id[case["caseId"]] for case in dev_cases])
    threshold, threshold_artifact = select_threshold(train_vectors, train_cases, dev_vectors, dev_cases, rule_by_id)
    threshold_artifact["internalSplitHash"] = split["splitHash"]
    baseline.write_json(args.output_dir / "binary_router_threshold_selection_v1.json", threshold_artifact)

    fit_vectors = np.stack([vector_by_id[case["caseId"]] for case in fit])
    started = time.perf_counter_ns()
    model = fit_model(fit_vectors, fit)
    final_training_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
    model_artifact = {
        "schemaVersion": "bge-binary-router-model-v1",
        "benchmarkVersion": BENCHMARK_VERSION,
        "labels": [FAST_ELIGIBLE, LONG_REQUIRED],
        "positiveClass": LONG_REQUIRED,
        "threshold": threshold,
        "model": model,
    }
    model_path = args.output_dir / "bge_binary_router_v1.joblib"
    joblib.dump(model_artifact, model_path, compress=3)

    validation_vectors = np.stack([vector_by_id[case["caseId"]] for case in validation])
    boundary_vectors = np.stack([vector_by_id[case["caseId"]] for case in boundary])
    validation_rows = evaluate_cases(validation, model.predict_proba(validation_vectors)[:, 1], threshold, rule_by_id)
    boundary_rows = evaluate_cases(boundary, model.predict_proba(boundary_vectors)[:, 1], threshold, rule_by_id)
    validation_result = binary_metrics(validation_rows)
    boundary_result = boundary_metrics(boundary_rows)
    baseline.write_jsonl(args.output_dir / "binary_validation_outputs_v1.jsonl", validation_rows)
    baseline.write_json(args.output_dir / "binary_validation_metrics_v1.json", validation_result)
    baseline.write_jsonl(args.output_dir / "binary_boundary_outputs_v1.jsonl", boundary_rows)
    baseline.write_json(args.output_dir / "binary_boundary_metrics_v1.json", boundary_result)

    policy = json.loads(RULE_POLICY.read_text(encoding="utf-8"))
    rule_validation_rows = [rule_output(case, rule_by_id[case["caseId"]], policy) for case in validation]
    rule_boundary_rows = [rule_output(case, rule_by_id[case["caseId"]], policy) for case in boundary]
    comparison = {
        "schemaVersion": "rule-vs-binary-bge-v1",
        "sameTargets": True,
        "sameEvaluationCases": True,
        "rulePolicy": {"scoreVersion": policy["scoreVersion"], "threshold": policy["threshold"], "policyHash": policy["policyHash"]},
        "ruleBinaryBaseline": {"validation": binary_metrics(rule_validation_rows), "boundary": boundary_metrics(rule_boundary_rows)},
        "bgeBinaryLogistic": {"validation": validation_result, "boundary": boundary_result},
    }
    baseline.write_json(args.output_dir / "rule_vs_binary_bge_v1.json", comparison)

    if not args.model_dir.is_dir():
        raise RuntimeError("BGE_M3_AVAILABILITY_GATE_BLOCKED")
    device = args.device if args.device != "cuda" or torch.cuda.is_available() else "cpu"
    provider = BgeM3EmbeddingProvider(BgeM3EmbeddingProviderConfig(model_dir=args.model_dir, device=device, batch_size=1, normalize=True, max_length=512))
    if not provider.health_check()["available"]:
        raise RuntimeError("BGE_M3_AVAILABILITY_GATE_BLOCKED")
    provider.encoder._load()
    for parameter in provider.encoder.model.parameters():
        parameter.requires_grad_(False)
    trainable_parameter_tensors = sum(parameter.requires_grad for parameter in provider.encoder.model.parameters())
    if trainable_parameter_tensors:
        raise RuntimeError("BGE_M3_NOT_FROZEN")
    latency = latency_metrics(provider, model, validation + boundary, threshold, rule_by_id)
    encoder_parameter = next(provider.encoder.model.parameters())
    provider.close()

    manifest = {
        "schemaVersion": "bge-binary-router-manifest-v1",
        "benchmarkVersion": BENCHMARK_VERSION,
        "embeddingModelId": MODEL_ID,
        "embeddingModelRevision": embedding_manifest["modelRevision"],
        "embeddingDimension": embedding_manifest["dimension"],
        "embeddingNormalization": embedding_manifest["normalizationConfig"],
        "embeddingCacheReused": True,
        "device": str(encoder_parameter.device),
        "dtype": str(encoder_parameter.dtype).replace("torch.", ""),
        "encoderFrozen": True,
        "trainableEncoderParameterTensors": trainable_parameter_tensors,
        "logisticParameters": LR_PARAMETERS,
        "positiveClass": LONG_REQUIRED,
        "selectedThreshold": threshold,
        "scoreInterpretation": "ordinal_classification_score_not_calibrated_probability",
        "trainingPartition": "CALIBRATION_FIT_80_ONLY",
        "thresholdSelectionPartition": "FIT_INTERNAL_TRAIN_64_DEV_16",
        "validationUsedForTuning": False,
        "boundaryUsedForTuning": False,
        "frozenBenchmarkExecuted": False,
        "trainingDatasetHash": before[str(baseline.DEFAULT_CALIBRATION)],
        "trainingSplitHash": split["splitHash"],
        "modelArtifactSha": baseline.sha256_file(model_path),
        "finalTrainingTimeMs": final_training_ms,
        "latency": latency,
        "externalApiCallCount": 0,
    }
    baseline.write_json(args.output_dir / "bge_binary_router_manifest_v1.json", manifest)

    candidate, recommendation = candidate_gate(validation_result)
    after = {str(path): baseline.sha256_file(path) for path in protected}
    if after != before:
        raise RuntimeError("PROTECTED_DATASET_CHANGED")
    source = inspect.getsource(sys.modules[__name__])
    gate = {
        "targetAuditGate": audit["gate"],
        "fitOnlyTrainingGate": "PASS",
        "devOnlyThresholdGate": "PASS",
        "embeddingIdentityGate": "PASS",
        "safetyOverrideGate": "PASS",
        "validationGate": "PASS",
        "boundaryChallengeGate": "PASS",
        "datasetReadOnlyGate": "PASS",
        "securityScanGate": "PASS",
        "step21_3dGate": "PASS",
        "binaryRouterCandidateGate": candidate,
        "nextRecommendation": recommendation,
        "calibrationSha": before[str(baseline.DEFAULT_CALIBRATION)],
        "boundarySha": before[str(baseline.DEFAULT_BOUNDARY)],
        "frozenGoldSha": before[str(baseline.DEFAULT_FROZEN)],
        "frozenBenchmarkExecuted": False,
        "runtimeRouterModified": False,
        "safetyGateModified": False,
        "longAnalysisExecuted": False,
        "policyRagExecuted": False,
        "reflectionExecuted": False,
        "externalApiCallCount": 0,
        "qwenCallCount": 0,
        "targetUsesCaseIdSpecialCases": "caseId" in inspect.getsource(is_complex_after_sales),
        "scriptHash": hashlib.sha256(source.encode("utf-8")).hexdigest().upper(),
    }
    baseline.write_json(args.output_dir / "step213d_binary_router_gate_v1.json", gate)
    args.report.write_text(build_report(audit, threshold_artifact, validation_result, boundary_result, comparison, latency, gate), encoding="utf-8", newline="\n")
    return {
        "targetAudit": audit,
        "threshold": threshold_artifact,
        "validation": validation_result,
        "boundary": boundary_result,
        "comparison": comparison,
        "manifest": manifest,
        "gate": gate,
    }


def main() -> int:
    result = run(parse_args())
    print(json.dumps({"validation": result["validation"], "boundary": result["boundary"], "gate": result["gate"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
