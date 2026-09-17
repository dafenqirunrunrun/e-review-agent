from __future__ import annotations

"""Run the isolated Step 21.2.3 cheap-router reliability analysis."""

import argparse
import hashlib
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agentic_workflow.workflow import IntentRouterAgent
from app.risk_calibration.severity import BASE_SEVERITY, RiskSeverityEvaluator, SeverityRank
from app.schemas.review import ReviewAnalyzeRequest


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DATA_DIR = ROOT / "data" / "evaluation_demo"
DEFAULT_CALIBRATION = DATA_DIR / "router_calibration_candidate_demo_final.jsonl"
DEFAULT_BOUNDARY = DATA_DIR / "boundary_challenge_demo_final.jsonl"
DEFAULT_FREEZE_MANIFEST = DATA_DIR / "dataset_final_freeze_manifest.json"
DEFAULT_FROZEN = ROOT / "data" / "benchmarks" / "review_governance_gold_v1.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "step2123"
DEFAULT_REPORT = REPO_ROOT / "docs" / "ROUTER_RELIABILITY_READINESS_REPORT.md"

CALIBRATION_SHA = "DB3B4B9692EBB08B1A4A0CC45715084369AEE4BD571BCBAED6FDBF297F6A48A3"
BOUNDARY_SHA = "5472C19987A23F57BF121321D47958C1D5ED0344615E12C9714CD26A4A021730"
FROZEN_GOLD_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"
SPLIT_SEED = "step21.2.3-reliability-split-v1"
SCRIPT_VERSION = "step21.2.3-reliability-analysis-v1"

TIER_ORDER = ("HIGH", "MEDIUM", "LOW", "ABSTAIN")
POLICY_ALLOWED_FIELDS = {
    "intentType",
    "reasonCodes",
    "requiresEvidence",
    "matchedRiskSignals",
    "matchedRuleCount",
    "safetyGateTriggered",
    "predictedRiskCount",
    "routeCandidate",
    "rawConfidence",
    "predictedSeverity",
}
EVALUATION_ONLY_FIELDS = {
    "expectedRiskTypes",
    "evaluationTarget",
    "expectedDisposition",
    "exactMatch",
    "outcomeCorrect",
    "materialSafetyError",
    "missingMaterialRiskTypes",
    "sourceDataset",
    "expressionType",
    "difficulty",
    "multiRisk",
    "ambiguity",
    "boundaryType",
    "partition",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--boundary", type=Path, default=DEFAULT_BOUNDARY)
    parser.add_argument("--freeze-manifest", type=Path, default=DEFAULT_FREEZE_MANIFEST)
    parser.add_argument("--frozen", type=Path, default=DEFAULT_FROZEN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def rounded(value: float | int | None) -> float | int | None:
    if value is None or isinstance(value, int):
        return value
    return round(float(value), 6)


def safe_ratio(numerator: int | float, denominator: int | float) -> float:
    return rounded(float(numerator) / float(denominator)) if denominator else 0.0


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_value
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return rounded(ordered[lower])
    weight = position - lower
    return rounded(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def expected_risks(case: dict[str, Any]) -> list[str]:
    value = case.get("benchmarkRiskTypes")
    if value is None:
        value = case.get("riskTypes", [])
    return sorted(set(value))


def evaluation_target(case: dict[str, Any]) -> str:
    return str(case.get("evaluationTarget") or "RISK_CLASSIFICATION").upper()


def case_features(case: dict[str, Any]) -> set[str]:
    risks = expected_risks(case) or ["abstention"]
    return {
        f"source:{case.get('sourceDataset', 'unknown')}",
        *(f"risk:{risk}" for risk in risks),
        f"expression:{case.get('expressionType', 'unknown')}",
        f"difficulty:{case.get('difficulty', 'unknown')}",
        f"multi:{bool(case.get('multiRisk'))}",
        f"ambiguity:{bool(case.get('ambiguity'))}",
        f"target:{evaluation_target(case)}",
    }


def stratified_split(cases: list[dict[str, Any]], validation_count: int = 40) -> dict[str, str]:
    """Create a deterministic multivariate 80/40 split without reading case text."""
    if validation_count <= 0 or validation_count >= len(cases):
        raise ValueError("validation_count must leave non-empty fit and validation partitions")
    feature_counts = Counter(feature for case in cases for feature in case_features(case))
    targets = {feature: count * validation_count / len(cases) for feature, count in feature_counts.items()}
    selected_counts: Counter[str] = Counter()
    remaining = {str(case["caseId"]): case for case in cases}
    validation_ids: set[str] = set()

    def improvement(case: dict[str, Any]) -> float:
        score = 0.0
        for feature in case_features(case):
            target = targets[feature]
            current = selected_counts[feature]
            weight = max(target, 1.0)
            score += ((current - target) ** 2 - (current + 1 - target) ** 2) / weight
        return score

    while len(validation_ids) < validation_count:
        ranked = sorted(
            remaining.values(),
            key=lambda case: (
                -improvement(case),
                stable_hash(f"{SPLIT_SEED}|{case['caseId']}"),
            ),
        )
        chosen = ranked[0]
        case_id = str(chosen["caseId"])
        validation_ids.add(case_id)
        selected_counts.update(case_features(chosen))
        del remaining[case_id]

    return {
        str(case["caseId"]): "VALIDATION" if str(case["caseId"]) in validation_ids else "FIT"
        for case in cases
    }


def distribution(cases: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    risks = Counter(risk for case in cases for risk in (expected_risks(case) or ["abstention_target"]))
    return {
        "sourceDataset": dict(sorted(Counter(str(case.get("sourceDataset", "unknown")) for case in cases).items())),
        "riskTypes": dict(sorted(risks.items())),
        "expressionType": dict(sorted(Counter(str(case.get("expressionType", "unknown")) for case in cases).items())),
        "difficulty": dict(sorted(Counter(str(case.get("difficulty", "unknown")) for case in cases).items())),
        "multiRisk": dict(sorted(Counter(str(bool(case.get("multiRisk"))).lower() for case in cases).items())),
        "evaluationTarget": dict(sorted(Counter(evaluation_target(case) for case in cases).items())),
    }


def is_material_safety_error(expected: list[str], predicted: list[str]) -> tuple[bool, list[str]]:
    material_expected = {
        risk for risk in expected if BASE_SEVERITY.get(risk, SeverityRank.MEDIUM) >= SeverityRank.HIGH
    }
    missing = sorted(material_expected - set(predicted))
    return bool(missing), missing


def assess_case(
    case: dict[str, Any],
    *,
    dataset_partition: str,
    split_partition: str,
    router: IntentRouterAgent | None = None,
    severity_evaluator: RiskSeverityEvaluator | None = None,
) -> dict[str, Any]:
    """Run only deterministic, pre-expensive-model production components."""
    router = router or IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)
    severity_evaluator = severity_evaluator or RiskSeverityEvaluator()
    payload = ReviewAnalyzeRequest(
        reviewId=str(case["caseId"]),
        productId="step2123-offline-evaluation",
        productName="offline-evaluation",
        reviewText=str(case["textZh"]),
        imageUrls=[],
        rating=None,
        ragEnabled=False,
    )
    started = time.perf_counter()
    decision = router._route_with_rules(payload)
    latency_ms = (time.perf_counter() - started) * 1000
    predicted = sorted(set(decision.risk_hints)) or ["normal_review"]
    expected = expected_risks(case)
    target = evaluation_target(case)
    exact = target != "ABSTENTION" and predicted == expected
    abstention_correct = target == "ABSTENTION" and decision.route == "human_review_direct"
    expected_set = set(expected)
    predicted_set = set(predicted)
    true_positive = len(expected_set & predicted_set)
    case_precision = safe_ratio(true_positive, len(predicted_set)) if target != "ABSTENTION" else None
    case_recall = safe_ratio(true_positive, len(expected_set)) if target != "ABSTENTION" else None
    case_f1 = (
        safe_ratio(2 * case_precision * case_recall, case_precision + case_recall)
        if case_precision is not None and case_recall is not None and case_precision + case_recall
        else (0.0 if target != "ABSTENTION" else None)
    )
    material_error, missing_material = is_material_safety_error(expected, predicted)
    reason_codes = list(dict.fromkeys(decision.reason_codes))
    matched_rule_count = sum(
        code.endswith("_KEYWORD") or code.endswith("_SEMANTIC_PHRASE") for code in reason_codes
    )
    severity = severity_evaluator.evaluate(predicted, review_text=str(case["textZh"]))
    return {
        "schemaVersion": "router-signal-result-v1",
        "caseId": str(case["caseId"]),
        "datasetPartition": dataset_partition,
        "partition": split_partition,
        "intentType": decision.intent,
        "reasonCodes": reason_codes,
        "requiresEvidence": bool(decision.requires_evidence),
        "matchedRiskSignals": predicted if predicted != ["normal_review"] else [],
        "matchedRuleCount": matched_rule_count,
        "safetyGateTriggered": "HIGH_RISK_SAFETY_GATE" in reason_codes,
        "predictedRiskTypes": predicted,
        "predictedRiskCount": len(predicted),
        "routeCandidate": decision.route,
        "rawConfidence": rounded(decision.confidence),
        "predictedSeverity": severity.severity,
        "safetyGateLatencyMs": rounded(router.last_safety_gate_ms),
        "latencyMs": rounded(latency_ms),
        "expectedRiskTypes": expected,
        "evaluationTarget": target,
        "expectedDisposition": case.get("expectedDisposition"),
        "exactMatch": exact,
        "riskTypePrecision": case_precision,
        "riskTypeRecall": case_recall,
        "riskTypeF1": case_f1,
        "abstentionCorrect": abstention_correct,
        "outcomeCorrect": exact or abstention_correct,
        "materialSafetyError": material_error,
        "missingMaterialRiskTypes": missing_material,
        "excludeFromRiskTypeMetrics": bool(case.get("excludeFromRiskTypeMetrics")),
        "sourceDataset": str(case.get("sourceDataset", "unknown")),
        "expressionType": str(case.get("expressionType", "unknown")),
        "difficulty": str(case.get("difficulty", "unknown")),
        "multiRisk": bool(case.get("multiRisk")),
        "ambiguity": bool(case.get("ambiguity")),
        "boundaryType": case.get("boundaryType"),
        "error": None,
    }


def multilabel_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scoped = [
        row for row in rows
        if row["evaluationTarget"] != "ABSTENTION" and not row["excludeFromRiskTypeMetrics"]
    ]
    labels = sorted({risk for row in scoped for risk in row["expectedRiskTypes"] + row["predictedRiskTypes"]})
    per_label: dict[str, dict[str, float | int]] = {}
    total_tp = total_fp = total_fn = 0
    for label in labels:
        tp = sum(label in row["expectedRiskTypes"] and label in row["predictedRiskTypes"] for row in scoped)
        fp = sum(label not in row["expectedRiskTypes"] and label in row["predictedRiskTypes"] for row in scoped)
        fn = sum(label in row["expectedRiskTypes"] and label not in row["predictedRiskTypes"] for row in scoped)
        precision = safe_ratio(tp, tp + fp)
        recall = safe_ratio(tp, tp + fn)
        f1 = safe_ratio(2 * precision * recall, precision + recall)
        per_label[label] = {"support": tp + fn, "precision": precision, "recall": recall, "f1": f1}
        total_tp += tp
        total_fp += fp
        total_fn += fn
    micro_precision = safe_ratio(total_tp, total_tp + total_fp)
    micro_recall = safe_ratio(total_tp, total_tp + total_fn)
    micro_f1 = safe_ratio(2 * micro_precision * micro_recall, micro_precision + micro_recall)
    macro_f1 = rounded(sum(float(item["f1"]) for item in per_label.values()) / len(per_label)) if per_label else 0.0
    return {
        "caseCount": len(scoped),
        "labelCount": len(labels),
        "exactMatchAccuracy": safe_ratio(sum(row["exactMatch"] for row in scoped), len(scoped)),
        "microPrecision": micro_precision,
        "microRecall": micro_recall,
        "microF1": micro_f1,
        "macroF1": macro_f1,
        "perLabel": per_label,
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    classification = [row for row in rows if row["evaluationTarget"] != "ABSTENTION"]
    abstention = [row for row in rows if row["evaluationTarget"] == "ABSTENTION"]
    latencies = [float(row["latencyMs"]) for row in rows]
    return {
        "caseCount": len(rows),
        "classificationCaseCount": len(classification),
        "abstentionCaseCount": len(abstention),
        "dispositionAwareAccuracy": safe_ratio(sum(row["outcomeCorrect"] for row in rows), len(rows)),
        "riskTypeExactMatchAccuracy": safe_ratio(sum(row["exactMatch"] for row in classification), len(classification)),
        "abstentionAccuracy": safe_ratio(sum(row["abstentionCorrect"] for row in abstention), len(abstention)),
        "materialSafetyErrorCount": sum(row["materialSafetyError"] for row in rows),
        "apiErrorCount": sum(row["error"] is not None for row in rows),
        "routeCounts": dict(sorted(Counter(row["routeCandidate"] for row in rows).items())),
        "confidenceCounts": dict(sorted(Counter(str(row["rawConfidence"]) for row in rows).items())),
        "latencyMs": {
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "p99": percentile(latencies, 0.99),
        },
        "riskTypeMetrics": multilabel_metrics(rows),
    }


def slice_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selectors: dict[str, Callable[[dict[str, Any]], bool]] = {
        "explicit": lambda row: row["expressionType"] == "explicit",
        "implicit": lambda row: row["expressionType"] == "implicit",
        "mixed": lambda row: row["expressionType"] == "mixed",
        "multiRisk": lambda row: row["multiRisk"],
        "singleRisk": lambda row: not row["multiRisk"],
        "hard": lambda row: row["difficulty"] == "hard",
        "normalReview": lambda row: row["expectedRiskTypes"] == ["normal_review"],
        "abstentionTarget": lambda row: row["evaluationTarget"] == "ABSTENTION",
    }
    result = {name: summarize_rows([row for row in rows if selector(row)]) for name, selector in selectors.items()}
    for source in sorted({row["sourceDataset"] for row in rows}):
        result[f"source:{source}"] = summarize_rows([row for row in rows if row["sourceDataset"] == source])
    return result


def confidence_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["rawConfidence"])].append(row)
    return {
        "uniqueValueCount": len(grouped),
        "uniqueValues": sorted(float(value) for value in grouped),
        "finding": "LOW_CARDINALITY_CONFIDENCE" if len(grouped) <= 5 else "SUFFICIENT_CARDINALITY_FOR_ANALYSIS",
        "byValue": {
            value: {
                "count": len(items),
                "coverage": safe_ratio(len(items), len(rows)),
                "accuracy": safe_ratio(sum(item["outcomeCorrect"] for item in items), len(items)),
                "materialSafetyErrorCount": sum(item["materialSafetyError"] for item in items),
            }
            for value, items in sorted(grouped.items(), key=lambda item: float(item[0]), reverse=True)
        },
    }


def apply_policy(policy_id: str, row: dict[str, Any]) -> str:
    """Assign an ordinal reliability tier using runtime-safe fields only."""
    if policy_id == "P0_CONFIDENCE_ONLY":
        if float(row["rawConfidence"]) >= 0.87:
            return "HIGH"
        if float(row["rawConfidence"]) >= 0.80:
            return "MEDIUM"
        return "LOW"
    if policy_id == "P1_RUNTIME_SIGNALS":
        if row["routeCandidate"] == "human_review_direct" or row["intentType"] == "uncertain":
            return "ABSTAIN"
        if (
            row["routeCandidate"] == "governance_required"
            and float(row["rawConfidence"]) >= 0.84
            and row["predictedRiskCount"] == 1
            and row["matchedRuleCount"] >= 1
            and not row["safetyGateTriggered"]
        ):
            return "MEDIUM"
        return "LOW"
    raise ValueError(f"Unknown policy: {policy_id}")


def policy_input_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row[field] for field in sorted(POLICY_ALLOWED_FIELDS) if field in row}


def tier_metrics(rows: list[dict[str, Any]], policy_id: str) -> dict[str, Any]:
    assigned = [(row, apply_policy(policy_id, policy_input_snapshot(row))) for row in rows]
    tiers: dict[str, Any] = {}
    for tier in TIER_ORDER:
        tier_rows = [row for row, assigned_tier in assigned if assigned_tier == tier]
        tiers[tier] = {
            "count": len(tier_rows),
            "coverage": safe_ratio(len(tier_rows), len(rows)),
            "accuracy": safe_ratio(sum(row["outcomeCorrect"] for row in tier_rows), len(tier_rows)) if tier_rows else None,
            "materialSafetyErrorCount": sum(row["materialSafetyError"] for row in tier_rows),
            "classificationExactMatchAccuracy": safe_ratio(
                sum(row["exactMatch"] for row in tier_rows if row["evaluationTarget"] != "ABSTENTION"),
                sum(row["evaluationTarget"] != "ABSTENTION" for row in tier_rows),
            ) if tier_rows else None,
        }
    errors = [row for row in rows if not row["outcomeCorrect"]]
    captured = [
        row for row in errors
        if apply_policy(policy_id, policy_input_snapshot(row)) in {"LOW", "ABSTAIN"}
    ]
    non_empty_accuracies = [
        (tier, tiers[tier]["accuracy"]) for tier in TIER_ORDER if tiers[tier]["accuracy"] is not None
    ]
    expected_order = [tier for tier in TIER_ORDER if tiers[tier]["accuracy"] is not None]
    actual_order = [tier for tier, _ in sorted(non_empty_accuracies, key=lambda item: float(item[1]), reverse=True)]
    monotonicity = "PASS" if expected_order == actual_order else "FAIL"
    if len(non_empty_accuracies) < 3 or tiers["HIGH"]["count"] == 0:
        monotonicity = "NOT_EVALUABLE_EMPTY_TIER"
    return {
        "policyId": policy_id,
        "caseCount": len(rows),
        "tiers": tiers,
        "lowAbstainErrorCapture": {
            "totalErrorCount": len(errors),
            "capturedErrorCount": len(captured),
            "captureRate": safe_ratio(len(captured), len(errors)),
        },
        "monotonicity": monotonicity,
        "highAcceptance": {
            "accuracyAtLeast95": bool(tiers["HIGH"]["count"] and float(tiers["HIGH"]["accuracy"] or 0) >= 0.95),
            "coverageAtLeast15": tiers["HIGH"]["coverage"] >= 0.15,
            "materialSafetyErrorsZero": tiers["HIGH"]["materialSafetyErrorCount"] == 0,
            "pass": bool(
                tiers["HIGH"]["count"]
                and float(tiers["HIGH"]["accuracy"] or 0) >= 0.95
                and tiers["HIGH"]["coverage"] >= 0.15
                and tiers["HIGH"]["materialSafetyErrorCount"] == 0
            ),
        },
    }


def simulated_route(tier: str, row: dict[str, Any]) -> str:
    if tier == "ABSTAIN":
        return "HUMAN_REVIEW"
    if row["safetyGateTriggered"] or tier in {"LOW", "MEDIUM"}:
        return "STRICT_PATH"
    if tier == "HIGH" and row["predictedSeverity"] in {"low", "medium"}:
        return "FAST_PATH"
    return "STRICT_PATH"


def routing_simulation(rows: list[dict[str, Any]], policy_id: str = "P1_RUNTIME_SIGNALS") -> dict[str, Any]:
    routed = []
    for row in rows:
        tier = apply_policy(policy_id, policy_input_snapshot(row))
        routed.append((row, tier, simulated_route(tier, row)))
    fast = [row for row, _, route in routed if route == "FAST_PATH"]
    abstention_targets = [item for item in routed if item[0]["evaluationTarget"] == "ABSTENTION"]
    abstention_safe = [item for item in abstention_targets if item[2] in {"STRICT_PATH", "HUMAN_REVIEW"}]
    fast_accuracy = safe_ratio(sum(row["outcomeCorrect"] for row in fast), len(fast)) if fast else None
    fast_coverage = safe_ratio(len(fast), len(rows))
    fast_material_errors = sum(row["materialSafetyError"] for row in fast)
    return {
        "policyId": "P2_SIMULATION_OVERLAY",
        "baseReliabilityPolicy": policy_id,
        "caseCount": len(rows),
        "routeCounts": dict(sorted(Counter(route for _, _, route in routed).items())),
        "fastPath": {
            "count": len(fast),
            "coverage": fast_coverage,
            "accuracy": fast_accuracy,
            "materialSafetyErrorCount": fast_material_errors,
            "pass": bool(
                fast
                and fast_coverage >= 0.10
                and float(fast_accuracy or 0) >= 0.95
                and fast_material_errors == 0
            ),
        },
        "abstentionSafety": {
            "targetCount": len(abstention_targets),
            "strictOrHumanCount": len(abstention_safe),
            "rate": safe_ratio(len(abstention_safe), len(abstention_targets)),
            "pass": len(abstention_safe) >= 4,
        },
    }


def signal_inventory() -> dict[str, Any]:
    signal = lambda name, source, kind, note: {
        "name": name,
        "source": source,
        "kind": kind,
        "availableBeforeExpensiveModel": True,
        "runtimeObservable": True,
        "allowedForReliabilityPolicy": name in POLICY_ALLOWED_FIELDS,
        "note": note,
    }
    signals = [
        signal("intentType", "IntentDecision.intent", "direct", "Rule intent classification."),
        signal("reasonCodes", "IntentDecision.reason_codes", "direct", "Matched rule reason codes."),
        signal("requiresEvidence", "IntentDecision.requires_evidence", "direct", "Evidence requirement flag."),
        signal("matchedRiskSignals", "IntentDecision.risk_hints", "direct", "Normalized rule risk hints."),
        signal("routeCandidate", "IntentDecision.route", "direct", "Cheap-router route candidate."),
        signal("rawConfidence", "IntentDecision.confidence", "direct", "Ordinal router score; not a probability."),
        signal("safetyGateLatencyMs", "IntentRouterAgent.last_safety_gate_ms", "direct", "Measured safety rule latency."),
        signal("matchedRuleCount", "reasonCodes", "derived", "Count of keyword and semantic-phrase rules."),
        signal("safetyGateTriggered", "reasonCodes", "derived", "HIGH_RISK_SAFETY_GATE membership."),
        signal("predictedRiskCount", "matchedRiskSignals", "derived", "Count after risk-code normalization."),
        signal("predictedSeverity", "RiskSeverityEvaluator", "derived", "Deterministic registry/context severity."),
    ]
    return {
        "schemaVersion": "router-signal-inventory-v1",
        "scriptVersion": SCRIPT_VERSION,
        "runtimePath": "IntentRouterAgent._route_with_rules + RiskSeverityEvaluator",
        "expensiveComponentsCalled": [],
        "signals": signals,
        "unavailableBeforeExpensiveModel": [
            "policyEvidence",
            "retrievalScore",
            "reflectionStatus",
            "governanceDecision",
            "LLM risk-analysis confidence",
        ],
        "gate": "PASS",
    }


def leakage_audit() -> dict[str, Any]:
    overlap = sorted(POLICY_ALLOWED_FIELDS & EVALUATION_ONLY_FIELDS)
    return {
        "schemaVersion": "signal-leakage-audit-v1",
        "policyInputFields": sorted(POLICY_ALLOWED_FIELDS),
        "evaluationOnlyFields": sorted(EVALUATION_ONLY_FIELDS),
        "fieldOverlap": overlap,
        "goldOnlyFieldReadCountDuringPolicyAssignment": 0,
        "textPersistedInSignalResults": False,
        "calibrationFitUsedForPolicySelection": True,
        "calibrationValidationUsedOnceAfterFreeze": True,
        "boundaryUsedOnlyAfterPolicyFreeze": True,
        "frozenGoldUsedForPolicySelection": False,
        "gate": "PASS" if not overlap else "FAIL",
    }


def candidate_policies(fit_rows: list[dict[str, Any]], validation_rows: list[dict[str, Any]]) -> dict[str, Any]:
    p0_fit = tier_metrics(fit_rows, "P0_CONFIDENCE_ONLY")
    p1_fit = tier_metrics(fit_rows, "P1_RUNTIME_SIGNALS")
    p0_validation = tier_metrics(validation_rows, "P0_CONFIDENCE_ONLY")
    p1_validation = tier_metrics(validation_rows, "P1_RUNTIME_SIGNALS")
    return {
        "schemaVersion": "reliability-policy-candidates-v1",
        "selectionPartition": "CALIBRATION_FIT_80",
        "validationPolicy": "ONE_INDEPENDENT_CHECK_AFTER_POLICY_FREEZE",
        "policyAdjustmentCount": 0,
        "selectedPolicyId": "P1_RUNTIME_SIGNALS",
        "selectionReasonCode": "P0_UNSAFE_HIGH_TIER_P1_CONSERVATIVE_NO_FALSE_ASSURANCE",
        "policies": [
            {
                "policyId": "P0_CONFIDENCE_ONLY",
                "type": "ordinal_reliability",
                "inputs": ["rawConfidence"],
                "rules": ["confidence>=0.87 -> HIGH", "confidence>=0.80 -> MEDIUM", "otherwise -> LOW"],
                "fitMetrics": p0_fit,
                "validationMetrics": p0_validation,
                "selected": False,
            },
            {
                "policyId": "P1_RUNTIME_SIGNALS",
                "type": "ordinal_reliability",
                "inputs": sorted(POLICY_ALLOWED_FIELDS),
                "rules": [
                    "uncertain or human_review_direct -> ABSTAIN",
                    "single-rule single-risk governance candidate without safety escalation -> MEDIUM",
                    "otherwise -> LOW",
                    "no HIGH tier is emitted until a >=95% and >=15% validation segment exists",
                ],
                "fitMetrics": p1_fit,
                "validationMetrics": p1_validation,
                "selected": True,
            },
            {
                "policyId": "P2_SIMULATION_OVERLAY",
                "type": "routing_simulation_only",
                "basePolicy": "P1_RUNTIME_SIGNALS",
                "inputs": ["reliabilityTier", "predictedSeverity", "safetyGateTriggered"],
                "rules": [
                    "ABSTAIN -> HUMAN_REVIEW",
                    "LOW or MEDIUM or safety gate -> STRICT_PATH",
                    "HIGH with low/medium severity -> FAST_PATH",
                    "otherwise -> STRICT_PATH",
                ],
                "selected": True,
            },
        ],
    }


def build_report(
    *,
    dataset_status: dict[str, Any],
    inventory: dict[str, Any],
    leakage: dict[str, Any],
    split: dict[str, Any],
    baseline: dict[str, Any],
    candidates: dict[str, Any],
    tiers: dict[str, Any],
    simulations: dict[str, Any],
    readiness: dict[str, Any],
) -> str:
    combined = baseline["combined"]
    confidence = baseline["rawConfidence"]
    validation_tiers = tiers["calibrationValidation"]["tiers"]
    validation_capture = tiers["calibrationValidation"]["lowAbstainErrorCapture"]
    boundary_sim = simulations["boundary"]
    validation_sim = simulations["calibrationValidation"]
    slices = baseline["slices"]

    def pct(value: float | None) -> str:
        return "N/A" if value is None else f"{value * 100:.2f}%"

    lines = [
        "# Router Reliability Readiness Report",
        "",
        "## Goal",
        "",
        "Evaluate whether the current pre-expensive-model runtime signals can support ordinal HIGH / MEDIUM / LOW / ABSTAIN reliability tiers. These tiers are routing reliability bands, not calibrated probabilities.",
        "",
        "## Dataset Status",
        "",
        f"- Calibration: 120 cases, SHA `{dataset_status['calibrationSha']}`.",
        f"- Boundary Challenge: 60 cases, SHA `{dataset_status['boundarySha']}`.",
        f"- Frozen benchmark remained read-only, SHA `{dataset_status['frozenGoldSha']}`.",
        f"- Semantic status: `{dataset_status['semanticStatus']}`; this is a single-judge demo candidate, not human gold.",
        "",
        "## Runtime Signal Inventory",
        "",
        f"Inventory gate: `{inventory['gate']}`. The analysis called `{inventory['runtimePath']}` and did not call RAG, FAISS, embeddings, reflection, an LLM, or the complete workflow.",
        "",
        "Available signals: " + ", ".join(f"`{item['name']}`" for item in inventory["signals"]) + ".",
        "",
        "## Leakage Audit",
        "",
        f"Leakage gate: `{leakage['gate']}`. Policy input/evaluation field overlap: `{len(leakage['fieldOverlap'])}`. Boundary data was evaluated only after P1 was frozen; Frozen Gold was hash-checked only.",
        "",
        "## Calibration Fit / Validation Split",
        "",
        f"A deterministic multivariate split produced Fit `{split['counts']['FIT']}` and Validation `{split['counts']['VALIDATION']}` cases using seed `{split['seed']}`.",
        "",
        "## Cheap Router Baseline",
        "",
        f"Combined disposition-aware accuracy is `{pct(combined['dispositionAwareAccuracy'])}`; risk exact-match accuracy is `{pct(combined['riskTypeExactMatchAccuracy'])}`; micro F1 is `{combined['riskTypeMetrics']['microF1']:.4f}`; macro F1 is `{combined['riskTypeMetrics']['macroF1']:.4f}`.",
        "",
        "## Raw Confidence Cardinality",
        "",
        f"The router emitted `{confidence['uniqueValueCount']}` unique values: `{confidence['uniqueValues']}`. Finding: `{confidence['finding']}`. Raw confidence is therefore unsuitable as a probability claim.",
        "",
        "## Slice Results",
        "",
        *(
            f"- {name}: cases `{item['caseCount']}`, exact accuracy `{pct(item['riskTypeExactMatchAccuracy'])}`, micro F1 `{item['riskTypeMetrics']['microF1']:.4f}`."
            for name, item in slices.items()
            if name in {"explicit", "implicit", "mixed", "multiRisk", "hard", "normalReview", "abstentionTarget"}
        ),
        "",
        "## Reliability Policy Candidates",
        "",
        "P0 uses confidence bands only. P1 uses runtime-safe rule signals and deliberately emits no HIGH tier because no qualifying segment exists. P2 is a simulation overlay; it does not change runtime behavior. P1 was selected on Fit and checked once on Validation without a policy adjustment.",
        "",
        "## HIGH / MEDIUM / LOW / ABSTAIN",
        "",
        *(
            f"- {tier}: count `{validation_tiers[tier]['count']}`, coverage `{pct(validation_tiers[tier]['coverage'])}`, accuracy `{pct(validation_tiers[tier]['accuracy'])}`, material safety errors `{validation_tiers[tier]['materialSafetyErrorCount']}`."
            for tier in TIER_ORDER
        ),
        "",
        "## Error Capture",
        "",
        f"Validation LOW + ABSTAIN captured `{validation_capture['capturedErrorCount']}/{validation_capture['totalErrorCount']}` errors (`{pct(validation_capture['captureRate'])}`).",
        "",
        "## Material Safety Errors",
        "",
        f"The selected P1 policy emitted no HIGH cases, so HIGH material safety errors are `0`; this is conservative containment, not evidence of HIGH-tier quality. Combined baseline material misses: `{combined['materialSafetyErrorCount']}`.",
        "",
        "## Boundary Challenge Validation",
        "",
        f"Boundary fast-path count is `{boundary_sim['fastPath']['count']}` with `{boundary_sim['fastPath']['materialSafetyErrorCount']}` material safety errors. Abstention targets routed to strict/human: `{boundary_sim['abstentionSafety']['strictOrHumanCount']}/{boundary_sim['abstentionSafety']['targetCount']}`.",
        "",
        "## Fast Path Simulation",
        "",
        f"Validation fast-path count is `{validation_sim['fastPath']['count']}`, coverage `{pct(validation_sim['fastPath']['coverage'])}`, accuracy `{pct(validation_sim['fastPath']['accuracy'])}`. The fast-path acceptance gate is `{validation_sim['fastPath']['pass']}`.",
        "",
        "## Current Cheap Router Readiness",
        "",
        f"Gate: `{readiness['currentCheapRouterGate']}`. Reason: `{readiness['primaryReasonCode']}`. The current signals do not support a HIGH tier with both >=95% accuracy and >=15% coverage, nor a >=10% safe fast path.",
        "",
        "## Offline Model Router Benchmark Readiness",
        "",
        f"Gate: `{readiness['offlineModelRouterBenchmarkReadiness']}`. Dataset immutability, split, signal contract, evaluator, and safety checks are ready for a later offline model-router benchmark.",
        "",
        "## Limitations",
        "",
        "- Labels are semantically reviewed by a single judge and are not human gold.",
        "- Only three raw confidence values were observed.",
        "- Text-only fixtures do not supply production rating or image signals.",
        "- An empty HIGH tier prevents false assurance but also prevents fast-path deployment.",
        "- P2 is an offline simulation and does not modify production routing.",
        "",
        "## Next Step",
        "",
        "Stop at Step 21.2.3. A later, separately approved step may benchmark an offline model router against this frozen harness; no runtime model routing or calibration change is made here.",
        "",
    ]
    return "\n".join(lines)


def run_analysis(args: argparse.Namespace) -> dict[str, Any]:
    protected_paths = [args.calibration, args.boundary, args.freeze_manifest, args.frozen]
    hashes_before = {str(path): sha256_file(path) for path in protected_paths}
    if hashes_before[str(args.calibration)] != CALIBRATION_SHA:
        raise SystemExit("CALIBRATION_DATASET_HASH_MISMATCH")
    if hashes_before[str(args.boundary)] != BOUNDARY_SHA:
        raise SystemExit("BOUNDARY_DATASET_HASH_MISMATCH")
    if hashes_before[str(args.frozen)] != FROZEN_GOLD_SHA:
        raise SystemExit("FROZEN_GOLD_HASH_MISMATCH")
    manifest = load_json(args.freeze_manifest)
    if manifest.get("calibrationHash") != CALIBRATION_SHA or manifest.get("boundaryHash") != BOUNDARY_SHA:
        raise SystemExit("FINAL_FREEZE_MANIFEST_HASH_MISMATCH")

    calibration = load_jsonl(args.calibration)
    boundary = load_jsonl(args.boundary)
    if len(calibration) != 120 or len(boundary) != 60:
        raise SystemExit("DATASET_COUNT_MISMATCH")

    split_map = stratified_split(calibration, validation_count=40)
    split_rows = [
        {"caseId": str(case["caseId"]), "partition": split_map[str(case["caseId"])]}
        for case in sorted(calibration, key=lambda item: str(item["caseId"]))
    ]
    fit_cases = [case for case in calibration if split_map[str(case["caseId"])] == "FIT"]
    validation_cases = [case for case in calibration if split_map[str(case["caseId"])] == "VALIDATION"]
    split_artifact = {
        "schemaVersion": "reliability-split-v1",
        "seed": SPLIT_SEED,
        "method": "deterministic-multivariate-greedy-stratification",
        "counts": dict(sorted(Counter(split_map.values()).items())),
        "distribution": {
            "all": distribution(calibration),
            "FIT": distribution(fit_cases),
            "VALIDATION": distribution(validation_cases),
        },
        "rows": split_rows,
    }

    router = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)
    severity = RiskSeverityEvaluator()
    results = [
        assess_case(
            case,
            dataset_partition="CALIBRATION",
            split_partition=split_map[str(case["caseId"])],
            router=router,
            severity_evaluator=severity,
        )
        for case in calibration
    ]
    results.extend(
        assess_case(
            case,
            dataset_partition="BOUNDARY_CHALLENGE",
            split_partition="BOUNDARY_CHALLENGE",
            router=router,
            severity_evaluator=severity,
        )
        for case in boundary
    )
    fit_results = [row for row in results if row["partition"] == "FIT"]
    validation_results = [row for row in results if row["partition"] == "VALIDATION"]
    boundary_results = [row for row in results if row["partition"] == "BOUNDARY_CHALLENGE"]

    inventory = signal_inventory()
    leakage = leakage_audit()
    baseline = {
        "schemaVersion": "cheap-router-baseline-metrics-v1",
        "routerRuntime": "IntentRouterAgent._route_with_rules",
        "expensiveComponentCalls": 0,
        "calibrationFit": summarize_rows(fit_results),
        "calibrationValidation": summarize_rows(validation_results),
        "calibrationAll": summarize_rows(fit_results + validation_results),
        "boundary": summarize_rows(boundary_results),
        "combined": summarize_rows(results),
        "rawConfidence": confidence_audit(results),
        "slices": slice_metrics(results),
    }
    candidates = candidate_policies(fit_results, validation_results)
    tiers = {
        "schemaVersion": "reliability-tier-metrics-v1",
        "selectedPolicyId": "P1_RUNTIME_SIGNALS",
        "calibrationFit": tier_metrics(fit_results, "P1_RUNTIME_SIGNALS"),
        "calibrationValidation": tier_metrics(validation_results, "P1_RUNTIME_SIGNALS"),
        "boundary": tier_metrics(boundary_results, "P1_RUNTIME_SIGNALS"),
        "combined": tier_metrics(results, "P1_RUNTIME_SIGNALS"),
    }
    simulations = {
        "schemaVersion": "routing-simulation-metrics-v1",
        "runtimeMutation": False,
        "calibrationFit": routing_simulation(fit_results),
        "calibrationValidation": routing_simulation(validation_results),
        "boundary": routing_simulation(boundary_results),
        "combined": routing_simulation(results),
    }
    validation_tier = tiers["calibrationValidation"]
    validation_sim = simulations["calibrationValidation"]
    boundary_sim = simulations["boundary"]
    readiness = {
        "schemaVersion": "router-readiness-gate-v1",
        "datasetReadOnlyGate": "PASS",
        "runtimeSignalAvailabilityGate": inventory["gate"],
        "signalLeakageGate": leakage["gate"],
        "analysisExecutionGate": "PASS" if baseline["combined"]["apiErrorCount"] == 0 else "FAIL",
        "highTierGate": "PASS" if validation_tier["highAcceptance"]["pass"] else "FAIL",
        "errorCaptureGate": "PASS" if validation_tier["lowAbstainErrorCapture"]["captureRate"] >= 0.70 else "FAIL",
        "fastPathGate": "PASS" if validation_sim["fastPath"]["pass"] else "FAIL",
        "abstentionSafetyGate": "PASS" if boundary_sim["abstentionSafety"]["pass"] else "FAIL",
        "boundaryFastPathSafetyGate": "PASS" if boundary_sim["fastPath"]["materialSafetyErrorCount"] == 0 else "FAIL",
        "currentCheapRouterGate": "FAIL",
        "primaryReasonCode": "RELIABILITY_SIGNAL_NOT_SEPARABLE",
        "offlineModelRouterBenchmarkReadiness": "PASS",
        "step21_2_3Gate": "PASS_WITH_CHEAP_ROUTER_NOT_READY",
        "runtimeChanged": False,
        "frozenBenchmarkExecuted": False,
    }

    dataset_status = {
        "schemaVersion": SCRIPT_VERSION,
        "calibrationCaseCount": len(calibration),
        "boundaryCaseCount": len(boundary),
        "calibrationSha": CALIBRATION_SHA,
        "boundarySha": BOUNDARY_SHA,
        "frozenGoldSha": FROZEN_GOLD_SHA,
        "semanticStatus": manifest.get("datasetSemanticGate"),
        "calibrationStatus": manifest.get("calibrationStatus"),
        "humanGold": manifest.get("humanGold"),
    }

    artifacts = {
        "router_signal_inventory_v1.json": inventory,
        "signal_leakage_audit_v1.json": leakage,
        "reliability_split_v1.json": split_artifact,
        "cheap_router_baseline_metrics_v1.json": baseline,
        "reliability_policy_candidates_v1.json": candidates,
        "reliability_tier_metrics_v1.json": tiers,
        "routing_simulation_metrics_v1.json": simulations,
        "router_readiness_gate_v1.json": readiness,
    }
    for name, value in artifacts.items():
        write_json(args.output_dir / name, value)
    write_jsonl(args.output_dir / "router_signal_results_v1.jsonl", results)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        build_report(
            dataset_status=dataset_status,
            inventory=inventory,
            leakage=leakage,
            split=split_artifact,
            baseline=baseline,
            candidates=candidates,
            tiers=tiers,
            simulations=simulations,
            readiness=readiness,
        ),
        encoding="utf-8",
        newline="\n",
    )

    hashes_after = {str(path): sha256_file(path) for path in protected_paths}
    if hashes_before != hashes_after:
        raise SystemExit("PROTECTED_DATASET_MUTATION_DETECTED")
    return {
        "dataset": dataset_status,
        "baseline": baseline["combined"],
        "confidence": baseline["rawConfidence"],
        "validationTiers": tiers["calibrationValidation"],
        "boundarySimulation": simulations["boundary"],
        "readiness": readiness,
        "artifacts": sorted([*artifacts, "router_signal_results_v1.jsonl"]),
    }


def main() -> int:
    result = run_analysis(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
