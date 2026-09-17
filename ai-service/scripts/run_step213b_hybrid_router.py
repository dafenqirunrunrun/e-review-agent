from __future__ import annotations

"""Run the offline Step 21.3B Rule + BGE semantic-guard simulation."""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.embedding_provider import BgeM3EmbeddingProvider, BgeM3EmbeddingProviderConfig
from app.risk_calibration.severity import RiskSeverityEvaluator
from scripts import run_step2123_reliability_analysis as baseline
from scripts import run_step213a2_discriminative_router as discriminative
from scripts import run_step213a_lite as qwen_base


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
STEP2123_DIR = ROOT / "artifacts" / "step2123"
STEP213A2_DIR = ROOT / "artifacts" / "step213a2_discriminative"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "step213b_hybrid"
DEFAULT_REPORT = REPO_ROOT / "docs" / "HYBRID_ROUTER_OFFLINE_SIMULATION_REPORT.md"
OOF_SEED = "step21.3b-fit80-oof5-v1"
FOLD_COUNT = 5
GUARD_THRESHOLDS = (0.30, 0.50, 0.70)
POLICY_NAMES = ("H1_CONSENSUS_GUARD", "H2_SEMANTIC_GUARD", "H3_RISK_PRESENCE_GUARD")
FAST_PATH = "FAST_PATH"
STRICT_PATH = "STRICT_PATH"
HUMAN_OR_ABSTAIN = "HUMAN_OR_ABSTAIN"

RULE_RUNTIME_FIELDS = (
    "predictedRiskTypes",
    "intentType",
    "reasonCodes",
    "requiresEvidence",
    "matchedRiskSignals",
    "matchedRuleCount",
    "safetyGateTriggered",
    "predictedSeverity",
    "routeCandidate",
)
BGE_RUNTIME_FIELDS = (
    "predictedRiskTypes",
    "classificationScores",
    "scoreSignals",
    "decision",
)
GOLD_ONLY_FIELDS = (
    "expectedRiskTypes",
    "goldRiskTypes",
    "goldSeverity",
    "difficulty",
    "boundaryType",
    "sourceDataset",
    "judgeResult",
    "exactMatch",
    "outcomeCorrect",
    "materialSafetyError",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=discriminative.DEFAULT_MODEL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    return parser.parse_args()


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def load_inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    fit, validation, boundary, _ = discriminative.load_partitions()
    rule_rows = qwen_base.load_jsonl(STEP2123_DIR / "router_signal_results_v1.jsonl")
    rule_by_id = {str(row["caseId"]): row for row in rule_rows}
    bge_rows = qwen_base.load_jsonl(STEP213A2_DIR / "bge_logistic_validation_outputs_v1.jsonl")
    bge_rows += qwen_base.load_jsonl(STEP213A2_DIR / "bge_logistic_boundary_outputs_v1.jsonl")
    bge_by_id = {str(row["caseId"]): row for row in bge_rows}
    all_case_ids = {str(case["caseId"]) for case in fit + validation + boundary}
    if (len(fit), len(validation), len(boundary)) != (80, 40, 60):
        raise RuntimeError("HYBRID_DATASET_PARTITION_COUNT_MISMATCH")
    if not all_case_ids.issubset(rule_by_id) or len(bge_by_id) != 100:
        raise RuntimeError("HYBRID_REQUIRED_PREDICTION_INPUT_MISSING")
    return fit, validation, boundary, rule_by_id, bge_by_id


def oof_features(case: dict[str, Any]) -> set[str]:
    risks = qwen_base.expected_risks(case)
    return {
        *(f"risk:{risk}" for risk in risks),
        f"target:{str(case.get('evaluationTarget') or 'RISK_CLASSIFICATION').upper()}",
        f"multi:{bool(case.get('multiRisk'))}",
        f"normal:{risks == ['normal_review']}",
        f"difficulty:{case.get('difficulty', 'unknown')}",
    }


def build_oof_split(fit_cases: list[dict[str, Any]]) -> dict[str, Any]:
    feature_totals = Counter(feature for case in fit_cases for feature in oof_features(case))
    targets = {feature: count / FOLD_COUNT for feature, count in feature_totals.items()}
    fold_counts = [Counter() for _ in range(FOLD_COUNT)]
    fold_rows: list[list[dict[str, Any]]] = [[] for _ in range(FOLD_COUNT)]

    def rarity(case: dict[str, Any]) -> float:
        return sum(1.0 / feature_totals[feature] for feature in oof_features(case))

    ordered = sorted(fit_cases, key=lambda case: (-rarity(case), baseline.stable_hash(f"{OOF_SEED}|{case['caseId']}")))
    for case in ordered:
        candidates = [fold for fold in range(FOLD_COUNT) if len(fold_rows[fold]) < len(fit_cases) // FOLD_COUNT]

        def assignment_cost(fold: int) -> tuple[float, str]:
            delta = 0.0
            for feature in oof_features(case):
                target = max(targets[feature], 1.0)
                before = fold_counts[fold][feature]
                delta += ((before + 1 - target) ** 2 - (before - target) ** 2) / target
            return delta, baseline.stable_hash(f"{OOF_SEED}|{case['caseId']}|{fold}")

        selected = min(candidates, key=assignment_cost)
        fold_rows[selected].append(case)
        fold_counts[selected].update(oof_features(case))

    rows = sorted(
        ({"caseId": str(case["caseId"]), "testFold": fold + 1} for fold, cases in enumerate(fold_rows) for case in cases),
        key=lambda row: row["caseId"],
    )
    folds = []
    for fold in range(FOLD_COUNT):
        test_ids = sorted(str(case["caseId"]) for case in fold_rows[fold])
        train_ids = sorted(str(case["caseId"]) for index, cases in enumerate(fold_rows) if index != fold for case in cases)
        folds.append({"fold": fold + 1, "trainCount": len(train_ids), "testCount": len(test_ids), "trainCaseIds": train_ids, "testCaseIds": test_ids})
    return {
        "schemaVersion": "hybrid-oof-split-v1",
        "seed": OOF_SEED,
        "method": "deterministic-multivariate-greedy-5-fold",
        "sourcePartition": "CALIBRATION_FIT_80",
        "foldCount": FOLD_COUNT,
        "rows": rows,
        "folds": folds,
        "splitHash": stable_hash(rows),
    }


def load_cached_vectors(cases: list[dict[str, Any]]) -> np.ndarray:
    manifest = json.loads((STEP213A2_DIR / "bge_m3_embedding_cache_manifest_v1.json").read_text(encoding="utf-8"))
    records = {str(row["caseId"]): row for row in manifest["records"]}
    vectors = []
    for case in cases:
        record = records.get(str(case["caseId"]))
        if not record:
            raise RuntimeError(f"HYBRID_EMBEDDING_CACHE_MISSING:{case['caseId']}")
        vector = np.load(STEP213A2_DIR / "embedding_cache" / f"{record['cacheKey']}.npy", allow_pickle=False).astype("float32")
        if vector.ndim != 1 or not np.isclose(np.linalg.norm(vector), 1.0, atol=1e-3):
            raise RuntimeError(f"HYBRID_EMBEDDING_CACHE_INVALID:{case['caseId']}")
        vectors.append(vector)
    return np.stack(vectors)


def bge_runtime_signal(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row[field] for field in BGE_RUNTIME_FIELDS}


def rule_runtime_signal(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row[field] for field in RULE_RUNTIME_FIELDS}


def policy_input(rule: dict[str, Any], bge: dict[str, Any]) -> dict[str, Any]:
    return {"rule": rule_runtime_signal(rule), "bge": bge_runtime_signal(bge)}


def non_normal(values: list[str]) -> set[str]:
    return set(values) - {"normal_review"}


def is_uncertain(signals: dict[str, Any]) -> bool:
    rule = signals["rule"]
    bge = signals["bge"]
    return rule["routeCandidate"] == "human_review_direct" or rule["intentType"] == "uncertain" or bge["decision"] == "ABSTAIN" or not bge["predictedRiskTypes"]


def h1_consensus(signals: dict[str, Any], _guard_threshold: float | None = None) -> tuple[str, list[str]]:
    if is_uncertain(signals):
        return HUMAN_OR_ABSTAIN, ["SIGNAL_UNCERTAIN"]
    if signals["rule"]["safetyGateTriggered"]:
        return STRICT_PATH, ["SAFETY_GATE_TRIGGERED"]
    if set(signals["rule"]["predictedRiskTypes"]) == set(signals["bge"]["predictedRiskTypes"]):
        return FAST_PATH, ["EXACT_RISK_CONSENSUS"]
    return STRICT_PATH, ["RISK_SET_DISAGREEMENT"]


def h2_semantic_guard(signals: dict[str, Any], guard_threshold: float | None = None) -> tuple[str, list[str]]:
    threshold = 0.50 if guard_threshold is None else guard_threshold
    if is_uncertain(signals):
        return HUMAN_OR_ABSTAIN, ["SIGNAL_UNCERTAIN"]
    rule = signals["rule"]
    bge = signals["bge"]
    rule_risks = non_normal(rule["predictedRiskTypes"])
    bge_risks = non_normal(bge["predictedRiskTypes"])
    reasons = []
    if rule["safetyGateTriggered"]:
        reasons.append("SAFETY_GATE_TRIGGERED")
    if not rule_risks and bge_risks:
        reasons.append("RULE_NORMAL_BGE_RISK")
    if len(bge_risks) >= 2 and not bge_risks.issubset(rule_risks):
        reasons.append("BGE_MULTI_RISK_NOT_COVERED")
    additional = bge_risks - rule_risks
    if any(float(bge["classificationScores"].get(risk, 0.0)) >= threshold for risk in additional):
        reasons.append("ADDITIONAL_RISK_ABOVE_GUARD_THRESHOLD")
    if bool(rule_risks) != bool(bge_risks):
        reasons.append("RISK_PRESENCE_CONFLICT")
    if reasons:
        return STRICT_PATH, list(dict.fromkeys(reasons))
    return FAST_PATH, ["NO_SEMANTIC_ESCALATION_SIGNAL"]


def h3_risk_presence(signals: dict[str, Any], _guard_threshold: float | None = None) -> tuple[str, list[str]]:
    if is_uncertain(signals):
        return HUMAN_OR_ABSTAIN, ["SIGNAL_UNCERTAIN"]
    rule = signals["rule"]
    rule_has_risk = bool(non_normal(rule["predictedRiskTypes"]))
    bge_has_risk = bool(non_normal(signals["bge"]["predictedRiskTypes"]))
    if rule["safetyGateTriggered"]:
        return STRICT_PATH, ["SAFETY_GATE_TRIGGERED"]
    if rule_has_risk != bge_has_risk:
        return STRICT_PATH, ["RISK_PRESENCE_CONFLICT"]
    return FAST_PATH, ["RISK_PRESENCE_CONSENSUS"]


POLICY_FUNCTIONS: dict[str, Callable[[dict[str, Any], float | None], tuple[str, list[str]]]] = {
    "H1_CONSENSUS_GUARD": h1_consensus,
    "H2_SEMANTIC_GUARD": h2_semantic_guard,
    "H3_RISK_PRESENCE_GUARD": h3_risk_presence,
}


def apply_policy(policy_name: str, signals: dict[str, Any], guard_threshold: float | None) -> tuple[str, list[str]]:
    return POLICY_FUNCTIONS[policy_name](signals, guard_threshold)


def evaluation_fields(case: dict[str, Any], rule: dict[str, Any], bge: dict[str, Any]) -> dict[str, Any]:
    return {
        "evaluationTarget": str(case.get("evaluationTarget") or "RISK_CLASSIFICATION").upper(),
        "expectedRiskTypes": qwen_base.expected_risks(case),
        "ruleExactMatch": bool(rule["exactMatch"]),
        "ruleOutcomeCorrect": bool(rule["outcomeCorrect"]),
        "bgeExactMatch": bool(bge["exactMatch"]),
        "bgeOutcomeCorrect": bool(bge["outcomeCorrect"]),
        "ruleMaterialSafetyError": bool(rule["materialSafetyError"]),
        "multiRisk": bool(case.get("multiRisk")),
        "difficulty": str(case.get("difficulty", "unknown")),
        "boundaryType": case.get("boundaryType"),
    }


def make_hybrid_row(case: dict[str, Any], rule: dict[str, Any], bge: dict[str, Any], policy_name: str, guard_threshold: float | None, *, fold: int | None = None) -> dict[str, Any]:
    signals = policy_input(rule, bge)
    if policy_name.startswith("H0_"):
        route, reason_codes = "UNSELECTED", []
    else:
        route, reason_codes = apply_policy(policy_name, signals, guard_threshold)
    evaluation = evaluation_fields(case, rule, bge)
    return {
        "schemaVersion": "hybrid-router-output-v1",
        "caseId": str(case["caseId"]),
        "datasetPartition": case["_partition"],
        "oofTestFold": fold,
        "policyName": policy_name,
        "guardThreshold": guard_threshold,
        "route": route,
        "routeReasonCodes": reason_codes,
        "finalRiskTypes": list(signals["rule"]["predictedRiskTypes"]),
        "ruleSignals": signals["rule"],
        "bgeSignals": signals["bge"],
        **evaluation,
    }


def oof_predictions(fit_cases: list[dict[str, Any]], vectors: np.ndarray, split: dict[str, Any], rule_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(case["caseId"]): index for index, case in enumerate(fit_cases)}
    fold_by_id = {str(row["caseId"]): int(row["testFold"]) for row in split["rows"]}
    rows = []
    for fold in range(1, FOLD_COUNT + 1):
        train_cases = [case for case in fit_cases if fold_by_id[str(case["caseId"])] != fold]
        test_cases = [case for case in fit_cases if fold_by_id[str(case["caseId"])] == fold]
        train_vectors = np.stack([vectors[by_id[str(case["caseId"])]] for case in train_cases])
        test_vectors = np.stack([vectors[by_id[str(case["caseId"])]] for case in test_cases])
        model, _ = discriminative.fit_heads(train_vectors, discriminative.multilabel_encode(train_cases))
        scores = discriminative.predict_scores(model, test_vectors)
        for index, case in enumerate(test_cases):
            bge = discriminative.classification_row(case, scores[index], 0.30)
            rule = rule_by_id[str(case["caseId"])]
            rows.append(make_hybrid_row(case, rule, bge, "H0_OOF_SIGNALS", None, fold=fold))
    rows.sort(key=lambda row: row["caseId"])
    if len(rows) != 80 or len({row["caseId"] for row in rows}) != 80:
        raise RuntimeError("HYBRID_OOF_PREDICTION_COVERAGE_INVALID")
    return rows


def micro_f1(rows: list[dict[str, Any]]) -> float:
    scoped = [row for row in rows if row["evaluationTarget"] != "ABSTENTION"]
    tp = fp = fn = 0
    for row in scoped:
        expected = set(row["expectedRiskTypes"])
        predicted = set(row["finalRiskTypes"])
        tp += len(expected & predicted)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
    precision = baseline.safe_ratio(tp, tp + fp)
    recall = baseline.safe_ratio(tp, tp + fn)
    return baseline.safe_ratio(2 * precision * recall, precision + recall)


def route_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fast = [row for row in rows if row["route"] == FAST_PATH]
    strict = [row for row in rows if row["route"] == STRICT_PATH]
    human = [row for row in rows if row["route"] == HUMAN_OR_ABSTAIN]
    rule_errors = [row for row in rows if not row["ruleOutcomeCorrect"]]
    multi_misses = [row for row in rows if row["multiRisk"] and not row["ruleExactMatch"]]
    material_errors = [row for row in rows if row["ruleMaterialSafetyError"]]
    correct = [row for row in rows if row["ruleOutcomeCorrect"]]
    abstention = [row for row in rows if row["evaluationTarget"] == "ABSTENTION"]
    captured = lambda selected: [row for row in selected if row["route"] != FAST_PATH]
    classification_fast = [row for row in fast if row["evaluationTarget"] != "ABSTENTION"]
    return {
        "caseCount": len(rows),
        "fastPath": {
            "count": len(fast),
            "coverage": baseline.safe_ratio(len(fast), len(rows)),
            "exactAccuracy": baseline.safe_ratio(sum(row["ruleExactMatch"] for row in classification_fast), len(classification_fast)),
            "microF1": micro_f1(fast),
            "materialSafetyErrorCount": sum(row["ruleMaterialSafetyError"] for row in fast),
        },
        "strictPath": {"count": len(strict), "coverage": baseline.safe_ratio(len(strict), len(rows))},
        "humanOrAbstain": {"count": len(human), "coverage": baseline.safe_ratio(len(human), len(rows))},
        "ruleErrorCapture": {"total": len(rule_errors), "captured": len(captured(rule_errors)), "rate": baseline.safe_ratio(len(captured(rule_errors)), len(rule_errors))},
        "multiRiskMissCapture": {"total": len(multi_misses), "captured": len(captured(multi_misses)), "rate": baseline.safe_ratio(len(captured(multi_misses)), len(multi_misses))},
        "materialSafetyErrorCapture": {"total": len(material_errors), "captured": len(captured(material_errors)), "rate": baseline.safe_ratio(len(captured(material_errors)), len(material_errors))},
        "falseEscalation": {"totalRuleCorrect": len(correct), "count": len(captured(correct)), "rate": baseline.safe_ratio(len(captured(correct)), len(correct))},
        "abstentionStrictCapture": {"targetCount": len(abstention), "captured": len(captured(abstention)), "rate": baseline.safe_ratio(len(captured(abstention)), len(abstention))},
    }


def simulate(base_rows: list[dict[str, Any]], policy_name: str, guard_threshold: float | None) -> list[dict[str, Any]]:
    rows = []
    for base in base_rows:
        signals = {"rule": base["ruleSignals"], "bge": base["bgeSignals"]}
        route, reasons = apply_policy(policy_name, signals, guard_threshold)
        rows.append({**base, "policyName": policy_name, "guardThreshold": guard_threshold, "route": route, "routeReasonCodes": reasons, "finalRiskTypes": list(base["ruleSignals"]["predictedRiskTypes"])})
    return rows


def complementarity(oof_rows: list[dict[str, Any]]) -> dict[str, Any]:
    quadrants = {
        "ruleCorrectBgeCorrect": sum(row["ruleOutcomeCorrect"] and row["bgeOutcomeCorrect"] for row in oof_rows),
        "ruleCorrectBgeWrong": sum(row["ruleOutcomeCorrect"] and not row["bgeOutcomeCorrect"] for row in oof_rows),
        "ruleWrongBgeCorrect": sum(not row["ruleOutcomeCorrect"] and row["bgeOutcomeCorrect"] for row in oof_rows),
        "ruleWrongBgeWrong": sum(not row["ruleOutcomeCorrect"] and not row["bgeOutcomeCorrect"] for row in oof_rows),
    }
    rule_errors = [row for row in oof_rows if not row["ruleOutcomeCorrect"]]
    disagreement = [row for row in rule_errors if set(row["ruleSignals"]["predictedRiskTypes"]) != set(row["bgeSignals"]["predictedRiskTypes"])]
    extra = [row for row in rule_errors if non_normal(row["bgeSignals"]["predictedRiskTypes"]) - non_normal(row["ruleSignals"]["predictedRiskTypes"])]
    multi = [row for row in rule_errors if len(non_normal(row["bgeSignals"]["predictedRiskTypes"])) >= 2]
    rule_normal_bge_risk = [row for row in rule_errors if not non_normal(row["ruleSignals"]["predictedRiskTypes"]) and non_normal(row["bgeSignals"]["predictedRiskTypes"])]

    def slice_quadrants(predicate: Callable[[dict[str, Any]], bool]) -> dict[str, int]:
        selected = [row for row in oof_rows if predicate(row)]
        return {
            "caseCount": len(selected),
            "ruleCorrectBgeCorrect": sum(row["ruleOutcomeCorrect"] and row["bgeOutcomeCorrect"] for row in selected),
            "ruleCorrectBgeWrong": sum(row["ruleOutcomeCorrect"] and not row["bgeOutcomeCorrect"] for row in selected),
            "ruleWrongBgeCorrect": sum(not row["ruleOutcomeCorrect"] and row["bgeOutcomeCorrect"] for row in selected),
            "ruleWrongBgeWrong": sum(not row["ruleOutcomeCorrect"] and not row["bgeOutcomeCorrect"] for row in selected),
        }

    return {
        "schemaVersion": "hybrid-complementarity-oof-v1",
        "caseCount": len(oof_rows),
        "quadrants": quadrants,
        "ruleErrorDetectionByBge": {
            "ruleErrorCount": len(rule_errors),
            "disagreementCount": len(disagreement),
            "disagreementRate": baseline.safe_ratio(len(disagreement), len(rule_errors)),
            "extraRiskSignalCount": len(extra),
            "extraRiskSignalRate": baseline.safe_ratio(len(extra), len(rule_errors)),
            "multiRiskSignalCount": len(multi),
            "multiRiskSignalRate": baseline.safe_ratio(len(multi), len(rule_errors)),
            "ruleNormalBgeRiskCount": len(rule_normal_bge_risk),
        },
        "slices": {
            "multiRisk": slice_quadrants(lambda row: row["multiRisk"]),
            "hard": slice_quadrants(lambda row: row["difficulty"] == "hard"),
            "normal": slice_quadrants(lambda row: row["expectedRiskTypes"] == ["normal_review"]),
            "materialSafetyRisk": slice_quadrants(lambda row: row["ruleMaterialSafetyError"]),
        },
    }


def rank_guard_threshold(metric: dict[str, Any]) -> tuple[Any, ...]:
    threshold = float(metric["guardThreshold"])
    return (
        metric["metrics"]["fastPath"]["materialSafetyErrorCount"] != 0,
        metric["metrics"]["fastPath"]["materialSafetyErrorCount"],
        -metric["metrics"]["ruleErrorCapture"]["rate"],
        -metric["metrics"]["multiRiskMissCapture"]["rate"],
        -metric["metrics"]["fastPath"]["exactAccuracy"],
        -metric["metrics"]["fastPath"]["coverage"],
        abs(threshold - 0.50),
        threshold,
    )


def rank_policy(candidate: dict[str, Any]) -> tuple[Any, ...]:
    metric = candidate["metrics"]
    return (
        metric["fastPath"]["materialSafetyErrorCount"] != 0,
        metric["fastPath"]["materialSafetyErrorCount"],
        -metric["fastPath"]["exactAccuracy"],
        -metric["ruleErrorCapture"]["rate"],
        -metric["multiRiskMissCapture"]["rate"],
        -metric["fastPath"]["coverage"],
        POLICY_NAMES.index(candidate["policyName"]),
    )


def select_policy(oof_rows: list[dict[str, Any]], split_hash: str) -> tuple[dict[str, Any], dict[str, Any]]:
    threshold_trials = []
    for threshold in GUARD_THRESHOLDS:
        threshold_trials.append({"guardThreshold": threshold, "metrics": route_metrics(simulate(oof_rows, "H2_SEMANTIC_GUARD", threshold))})
    selected_threshold_trial = min(threshold_trials, key=rank_guard_threshold)
    candidates = []
    for policy_name in POLICY_NAMES:
        guard_threshold = selected_threshold_trial["guardThreshold"] if policy_name == "H2_SEMANTIC_GUARD" else None
        candidates.append({"policyName": policy_name, "guardThreshold": guard_threshold, "metrics": route_metrics(simulate(oof_rows, policy_name, guard_threshold))})
    selected = min(candidates, key=rank_policy)
    candidate_artifact = {
        "schemaVersion": "hybrid-policy-candidates-v1",
        "selectionPartition": "CALIBRATION_FIT_80_OOF_ONLY",
        "validationUsed": False,
        "boundaryUsed": False,
        "frozenUsed": False,
        "guardThresholdCandidates": list(GUARD_THRESHOLDS),
        "h2GuardThresholdSelectionPriority": ["fastSafety", "ruleErrorCapture", "multiRiskMissCapture", "fastAccuracy", "coverage", "prefer0.50"],
        "h2GuardThresholdTrials": threshold_trials,
        "candidates": candidates,
    }
    policy_spec = {
        "policyName": selected["policyName"],
        "guardThreshold": selected["guardThreshold"],
        "selectionMetrics": selected["metrics"],
        "selectionPartition": "CALIBRATION_FIT_80_OOF_ONLY",
        "validationUsed": False,
        "boundaryUsed": False,
        "frozenUsed": False,
        "fitOofHash": stable_hash(oof_rows),
        "oofSplitHash": split_hash,
        "ruleOutputIsFinalClassification": True,
        "bgeRole": "SEMANTIC_GUARD_ONLY",
    }
    policy = {"schemaVersion": "hybrid-policy-selected-v1", **policy_spec, "policyHash": stable_hash(policy_spec), "frozen": True}
    return candidate_artifact, policy


def final_base_rows(cases: list[dict[str, Any]], rule_by_id: dict[str, dict[str, Any]], bge_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [make_hybrid_row(case, rule_by_id[str(case["caseId"])], bge_by_id[str(case["caseId"])], "H0_FROZEN_SIGNALS", None) for case in cases]


def boundary_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    overall = route_metrics(rows)
    by_type = {}
    for boundary_type in sorted({str(row["boundaryType"]) for row in rows}):
        by_type[boundary_type] = route_metrics([row for row in rows if str(row["boundaryType"]) == boundary_type])
    hard_negative = [row for row in rows if row["boundaryType"] == "hard_negative"]
    hard_fast = [row for row in hard_negative if row["route"] == FAST_PATH]
    overall["byBoundaryType"] = by_type
    overall["hardNegative"] = {
        "caseCount": len(hard_negative),
        "fastPathCount": len(hard_fast),
        "fastPathAccuracy": baseline.safe_ratio(sum(row["ruleExactMatch"] for row in hard_fast), len(hard_fast)) if hard_fast else None,
        "escalationRate": baseline.safe_ratio(len(hard_negative) - len(hard_fast), len(hard_negative)),
    }
    return overall


def leakage_audit() -> dict[str, Any]:
    used = sorted({*(f"rule.{field}" for field in RULE_RUNTIME_FIELDS), *(f"bge.{field}" for field in BGE_RUNTIME_FIELDS)})
    gold_overlap = sorted(field for field in GOLD_ONLY_FIELDS if any(value.endswith(f".{field}") for value in used))
    return {
        "schemaVersion": "hybrid-signal-leakage-audit-v1",
        "policyRuntimeInputs": used,
        "goldOnlyFields": list(GOLD_ONLY_FIELDS),
        "goldOnlySignalUsedByPolicy": len(gold_overlap),
        "overlap": gold_overlap,
        "gate": "PASS" if not gold_overlap else "FAIL",
    }


def latency_metrics(args: argparse.Namespace, cases: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    import torch

    if not args.model_dir.is_dir():
        raise RuntimeError("BGE_M3_AVAILABILITY_GATE_BLOCKED")
    manifest = json.loads((STEP213A2_DIR / "bge_m3_logistic_model_manifest_v1.json").read_text(encoding="utf-8"))
    model_path = STEP213A2_DIR / "bge_m3_logistic_router_v1.joblib"
    if baseline.sha256_file(model_path) != manifest["modelArtifactSha"]:
        raise RuntimeError("FROZEN_DISCRIMINATIVE_MODEL_HASH_MISMATCH")
    model = joblib.load(model_path)
    if float(model["globalThreshold"]) != 0.30:
        raise RuntimeError("FROZEN_DISCRIMINATIVE_THRESHOLD_MISMATCH")
    provider = BgeM3EmbeddingProvider(BgeM3EmbeddingProviderConfig(model_dir=args.model_dir, device=args.device, batch_size=1, normalize=True, max_length=512))
    if not provider.health_check()["available"]:
        raise RuntimeError("BGE_M3_AVAILABILITY_GATE_BLOCKED")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("BGE_M3_CUDA_UNAVAILABLE")
    router = baseline.IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)
    severity = RiskSeverityEvaluator()
    values = []
    provider.encoder._load()
    for parameter in provider.encoder.model.parameters():
        parameter.requires_grad_(False)
    for case in cases:
        started = time.perf_counter_ns()
        rule = baseline.assess_case(case, dataset_partition=case["_partition"], split_partition=case["_partition"], router=router, severity_evaluator=severity)
        vector = provider.encode_documents([str(case["textZh"])])
        scores = discriminative.predict_scores(model, vector)[0]
        bge = discriminative.classification_row(case, scores, 0.30)
        apply_policy(policy["policyName"], policy_input(rule, bge), policy["guardThreshold"])
        values.append((time.perf_counter_ns() - started) / 1_000_000)
    provider.close()
    return {
        "schemaVersion": "hybrid-latency-metrics-v1",
        "mode": "warm-single-request-batch-size-1",
        "caseCount": len(values),
        "p50Ms": baseline.percentile(values, 0.50),
        "p95Ms": baseline.percentile(values, 0.95),
        "p99Ms": baseline.percentile(values, 0.99),
        "components": ["Rule Router", "BGE-M3 embedding", "frozen logistic heads", "hybrid policy"],
        "externalApiCost": 0,
        "localComputeCostPresent": True,
    }


def build_report(complement: dict[str, Any], candidates: dict[str, Any], policy: dict[str, Any], validation: dict[str, Any], boundary: dict[str, Any], latency: dict[str, Any], gate: dict[str, Any]) -> str:
    quadrant = complement["quadrants"]
    selected = policy["selectionMetrics"]
    return "\n".join([
        "# Hybrid Router Offline Simulation Report", "",
        "## Scope", "",
        "Step 21.3B simulates Rule Router as the primary classifier and frozen BGE-M3 + logistic heads as a semantic routing guard. It changes no runtime code, never merges or overwrites Rule labels, executes no Frozen cases, and calls no external API.", "",
        "## Fit80 OOF Complementarity", "",
        f"Quadrants: `{json.dumps(quadrant, sort_keys=True)}`. Rule-error BGE disagreement rate: `{complement['ruleErrorDetectionByBge']['disagreementRate']:.4f}`.", "",
        "## Frozen Policy", "",
        f"Selected `{policy['policyName']}` with guard threshold `{policy['guardThreshold']}` from Fit80 OOF only. OOF fast coverage `{selected['fastPath']['coverage']:.4f}`, exact accuracy `{selected['fastPath']['exactAccuracy']:.4f}`, material safety errors `{selected['fastPath']['materialSafetyErrorCount']}`.", "",
        "## Validation", "",
        f"Fast `{validation['fastPath']['count']}` / `{validation['fastPath']['coverage']:.4f}`, exact `{validation['fastPath']['exactAccuracy']:.4f}`, safety errors `{validation['fastPath']['materialSafetyErrorCount']}`. Rule-error capture `{validation['ruleErrorCapture']['rate']:.4f}`, multi-risk miss capture `{validation['multiRiskMissCapture']['rate']:.4f}`, material safety capture `{validation['materialSafetyErrorCapture']['rate']:.4f}`, false escalation `{validation['falseEscalation']['rate']:.4f}`.", "",
        "## Boundary And Latency", "",
        f"Boundary fast/strict/human: `{boundary['fastPath']['count']}/{boundary['strictPath']['count']}/{boundary['humanOrAbstain']['count']}`; fast safety errors `{boundary['fastPath']['materialSafetyErrorCount']}`. Hybrid P50/P95 `{latency['p50Ms']}/{latency['p95Ms']} ms`.", "",
        "## Gates", "",
        *(f"- `{key}` = `{value}`" for key, value in gate.items() if key.endswith("Gate")), "",
        "## Conclusion", "",
        f"`{gate['nextRecommendation']}`", "",
    ])


def run(args: argparse.Namespace) -> dict[str, Any]:
    os.environ.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"})
    protected = [qwen_base.DEFAULT_CALIBRATION, qwen_base.DEFAULT_BOUNDARY, qwen_base.DEFAULT_FROZEN, qwen_base.DEFAULT_SPLIT, qwen_base.DEFAULT_RULE_RESULTS, STEP213A2_DIR / "bge_m3_logistic_router_v1.joblib"]
    before = {str(path): baseline.sha256_file(path) for path in protected}
    if before[str(qwen_base.DEFAULT_FROZEN)] != qwen_base.FROZEN_GOLD_SHA:
        raise RuntimeError("FROZEN_GOLD_HASH_MISMATCH")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    fit, validation, boundary, rule_by_id, bge_by_id = load_inputs()

    split = build_oof_split(fit)
    baseline.write_json(args.output_dir / "hybrid_oof_split_v1.json", split)
    fit_vectors = load_cached_vectors(fit)
    oof_rows = oof_predictions(fit, fit_vectors, split, rule_by_id)
    baseline.write_jsonl(args.output_dir / "hybrid_oof_predictions_v1.jsonl", oof_rows)

    complement = complementarity(oof_rows)
    leakage = leakage_audit()
    baseline.write_json(args.output_dir / "hybrid_complementarity_oof_v1.json", complement)
    baseline.write_json(args.output_dir / "hybrid_signal_leakage_audit_v1.json", leakage)
    if leakage["gate"] != "PASS":
        raise RuntimeError("HYBRID_SIGNAL_LEAKAGE_GATE_FAIL")

    candidates, policy = select_policy(oof_rows, split["splitHash"])
    baseline.write_json(args.output_dir / "hybrid_policy_candidates_v1.json", candidates)
    baseline.write_json(args.output_dir / "hybrid_policy_selected_v1.json", policy)

    validation_base = final_base_rows(validation, rule_by_id, bge_by_id)
    boundary_base = final_base_rows(boundary, rule_by_id, bge_by_id)
    validation_rows = simulate(validation_base, policy["policyName"], policy["guardThreshold"])
    boundary_rows = simulate(boundary_base, policy["policyName"], policy["guardThreshold"])
    validation_metric = route_metrics(validation_rows)
    boundary_metric = boundary_metrics(boundary_rows)
    baseline.write_jsonl(args.output_dir / "hybrid_validation_outputs_v1.jsonl", validation_rows)
    baseline.write_jsonl(args.output_dir / "hybrid_boundary_outputs_v1.jsonl", boundary_rows)
    baseline.write_json(args.output_dir / "hybrid_validation_metrics_v1.json", validation_metric)
    baseline.write_json(args.output_dir / "hybrid_boundary_metrics_v1.json", boundary_metric)

    latency = latency_metrics(args, validation + boundary, policy)
    baseline.write_json(args.output_dir / "hybrid_latency_metrics_v1.json", latency)

    fast = validation_metric["fastPath"]
    error_capture_pass = validation_metric["ruleErrorCapture"]["rate"] >= 0.70 and validation_metric["multiRiskMissCapture"]["rate"] >= 0.80
    safety_pass = fast["materialSafetyErrorCount"] == 0 and validation_metric["materialSafetyErrorCapture"]["rate"] >= 0.90
    boundary_abstention = boundary_metric["abstentionStrictCapture"]
    abstention_pass = boundary_abstention["targetCount"] == 5 and boundary_abstention["captured"] >= 4
    full_candidate = fast["exactAccuracy"] >= 0.95 and fast["coverage"] >= 0.10 and error_capture_pass and safety_pass and abstention_pass
    limited_candidate = fast["exactAccuracy"] >= 0.90 and fast["coverage"] >= 0.10 and error_capture_pass and safety_pass and abstention_pass
    candidate_gate = "PASS" if full_candidate else "PASS_WITH_LIMITATIONS" if limited_candidate else "FAIL"
    if fast["materialSafetyErrorCount"]:
        recommendation = "HYBRID_ROUTER_UNSAFE"
    elif fast["coverage"] < 0.10:
        recommendation = "HYBRID_ROUTER_TOO_CONSERVATIVE"
    elif candidate_gate != "FAIL":
        recommendation = "HYBRID_ROUTER_SHADOW_EVALUATION"
    else:
        recommendation = "HYBRID_RULE_SEMANTIC_COMPLEMENTARITY_LOW"
    gate = {
        "hybridOofGate": "PASS",
        "hybridSignalLeakageGate": leakage["gate"],
        "hybridPolicySelectionGate": "PASS",
        "hybridValidationGate": "PASS",
        "hybridErrorCaptureGate": "PASS" if error_capture_pass else "FAIL",
        "hybridSafetyGate": "PASS" if safety_pass else "FAIL",
        "hybridBoundaryGate": "PASS",
        "hybridAbstentionGate": "PASS" if abstention_pass else "FAIL",
        "hybridLatencyGate": "PASS" if latency["caseCount"] == 100 else "FAIL",
        "step21_3bGate": "PASS",
        "hybridRouterCandidateGate": candidate_gate,
        "calibrationSha": baseline.sha256_file(qwen_base.DEFAULT_CALIBRATION),
        "boundarySha": baseline.sha256_file(qwen_base.DEFAULT_BOUNDARY),
        "frozenGoldSha": baseline.sha256_file(qwen_base.DEFAULT_FROZEN),
        "frozenBenchmarkExecuted": False,
        "runtimeChanged": False,
        "externalApiCallCount": 0,
        "nextRecommendation": recommendation,
    }
    baseline.write_json(args.output_dir / "step213b_hybrid_gate_v1.json", gate)
    args.report.write_text(build_report(complement, candidates, policy, validation_metric, boundary_metric, latency, gate), encoding="utf-8", newline="\n")
    after = {str(path): baseline.sha256_file(path) for path in protected}
    if before != after:
        raise RuntimeError("PROTECTED_INPUT_MUTATION_DETECTED")
    return {"complementarity": complement, "candidates": candidates, "policy": policy, "validation": validation_metric, "boundary": boundary_metric, "latency": latency, "gate": gate}


def main() -> int:
    result = run(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
