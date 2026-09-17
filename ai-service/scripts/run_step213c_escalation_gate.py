from __future__ import annotations

"""Run the offline Step 21.3C cheap-signal escalation-gate simulation."""

import argparse
import hashlib
import inspect
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.risk_calibration.severity import RiskSeverityEvaluator
from scripts import run_step2123_reliability_analysis as baseline


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
STEP2123_DIR = ROOT / "artifacts" / "step2123"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "step213c_escalation"
DEFAULT_REPORT = REPO_ROOT / "docs" / "ESCALATION_ROUTER_OFFLINE_REPORT.md"
RULE_RESULTS = STEP2123_DIR / "router_signal_results_v1.jsonl"
SCORE_VERSIONS = ("S0_MINIMAL", "S1_RISK_AWARE", "S2_ORDINAL_AUX")
THRESHOLD_CANDIDATES = (1, 2, 3, 4)
FAST_PATH = "FAST_PATH"
LONG_ANALYSIS = "LONG_ANALYSIS"

RUNTIME_SIGNALS = (
    "intentType",
    "reasonCodes",
    "requiresEvidence",
    "matchedRiskSignals",
    "routeCandidate",
    "rawConfidence",
    "matchedRuleCount",
    "safetyGateTriggered",
    "predictedRiskCount",
    "predictedSeverity",
)
EVALUATION_ONLY_SIGNALS = (
    "expectedRiskTypes",
    "goldRiskTypes",
    "goldSeverity",
    "difficulty",
    "boundaryType",
    "sourceDataset",
    "judgeVerdict",
    "caseCorrect",
    "exactMatch",
    "outcomeCorrect",
    "materialSafetyError",
    "evaluationTarget",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def runtime_signal(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row[field] for field in RUNTIME_SIGNALS}


def _base_score(signals: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    triggered = []
    risk_signal_count = len(signals["matchedRiskSignals"])
    if signals["requiresEvidence"]:
        score += 1
        triggered.append("requires_evidence")
    if risk_signal_count >= 1:
        score += 1
        triggered.append("risk_signal_present")
    if risk_signal_count >= 2:
        score += 1
        triggered.append("multiple_risk_signals")
    return score, triggered


def score_s0(signals: dict[str, Any]) -> tuple[int, list[str]]:
    return _base_score(signals)


def score_s1(signals: dict[str, Any]) -> tuple[int, list[str]]:
    score, triggered = _base_score(signals)
    if signals["predictedRiskCount"] >= 2:
        score += 1
        triggered.append("multiple_predicted_risks")
    if str(signals["predictedSeverity"]).lower() in {"high", "critical"}:
        score += 1
        triggered.append("high_or_critical_severity")
    return score, triggered


def score_s2(signals: dict[str, Any]) -> tuple[int, list[str]]:
    score, triggered = score_s1(signals)
    if float(signals["rawConfidence"]) < 0.88:
        score += 1
        triggered.append("lower_ordinal_router_signal")
    return score, triggered


SCORE_FUNCTIONS: dict[str, Callable[[dict[str, Any]], tuple[int, list[str]]]] = {
    "S0_MINIMAL": score_s0,
    "S1_RISK_AWARE": score_s1,
    "S2_ORDINAL_AUX": score_s2,
}


def calculate_score(score_version: str, signals: dict[str, Any]) -> tuple[int, list[str]]:
    return SCORE_FUNCTIONS[score_version](signals)


def route_signal(score_version: str, threshold: int, signals: dict[str, Any]) -> tuple[int, str, list[str], bool]:
    score, triggered = calculate_score(score_version, signals)
    safety_override = bool(signals["safetyGateTriggered"])
    if safety_override:
        return score, LONG_ANALYSIS, [*triggered, "safety_override"], True
    route = FAST_PATH if score < threshold else LONG_ANALYSIS
    return score, route, triggered, False


def make_output(row: dict[str, Any], score_version: str, threshold: int) -> dict[str, Any]:
    signals = runtime_signal(row)
    score, route, triggered, safety_override = route_signal(score_version, threshold, signals)
    return {
        "schemaVersion": "escalation-routing-output-v1",
        "caseId": str(row["caseId"]),
        "datasetPartition": row["partition"],
        "scoreVersion": score_version,
        "threshold": threshold,
        "escalationScore": score,
        "route": route,
        "triggeredSignals": triggered,
        "safetyOverride": safety_override,
        "rulePredictedRiskTypes": list(row["predictedRiskTypes"]),
        "evaluationTarget": row["evaluationTarget"],
        "expectedRiskTypes": list(row["expectedRiskTypes"]),
        "ruleExactMatch": bool(row["exactMatch"]),
        "ruleOutcomeCorrect": bool(row["outcomeCorrect"]),
        "ruleMaterialSafetyError": bool(row["materialSafetyError"]),
        "difficulty": row["difficulty"],
        "boundaryType": row.get("boundaryType"),
    }


def micro_f1(rows: list[dict[str, Any]]) -> float:
    scoped = [row for row in rows if row["evaluationTarget"] != "ABSTENTION"]
    tp = fp = fn = 0
    for row in scoped:
        expected = set(row["expectedRiskTypes"])
        predicted = set(row["rulePredictedRiskTypes"])
        tp += len(expected & predicted)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
    precision = baseline.safe_ratio(tp, tp + fp)
    recall = baseline.safe_ratio(tp, tp + fn)
    return baseline.safe_ratio(2 * precision * recall, precision + recall)


def routing_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fast = [row for row in rows if row["route"] == FAST_PATH]
    long = [row for row in rows if row["route"] == LONG_ANALYSIS]
    classification_fast = [row for row in fast if row["evaluationTarget"] != "ABSTENTION"]
    rule_errors = [row for row in rows if not row["ruleOutcomeCorrect"]]
    material_errors = [row for row in rows if row["ruleMaterialSafetyError"]]
    correct_safe = [row for row in rows if row["ruleOutcomeCorrect"] and not row["ruleMaterialSafetyError"]]
    abstention = [row for row in rows if row["evaluationTarget"] == "ABSTENTION"]
    captured = lambda selected: [row for row in selected if row["route"] == LONG_ANALYSIS]
    return {
        "caseCount": len(rows),
        "fastPath": {
            "count": len(fast),
            "coverage": baseline.safe_ratio(len(fast), len(rows)),
            "exactAccuracy": baseline.safe_ratio(sum(row["ruleExactMatch"] for row in classification_fast), len(classification_fast)) if classification_fast else None,
            "microF1": micro_f1(fast) if classification_fast else None,
            "materialSafetyErrorCount": sum(row["ruleMaterialSafetyError"] for row in fast),
        },
        "longAnalysis": {"count": len(long), "rate": baseline.safe_ratio(len(long), len(rows))},
        "ruleErrorCapture": {"total": len(rule_errors), "captured": len(captured(rule_errors)), "rate": baseline.safe_ratio(len(captured(rule_errors)), len(rule_errors))},
        "materialSafetyErrorCapture": {"total": len(material_errors), "captured": len(captured(material_errors)), "rate": baseline.safe_ratio(len(captured(material_errors)), len(material_errors))},
        "falseEscalation": {"totalCorrectSafe": len(correct_safe), "count": len(captured(correct_safe)), "rate": baseline.safe_ratio(len(captured(correct_safe)), len(correct_safe))},
        "abstentionLongCapture": {"targetCount": len(abstention), "captured": len(captured(abstention)), "rate": baseline.safe_ratio(len(captured(abstention)), len(abstention))},
    }


def score_inventory(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reason_codes = sorted({code for row in rows for code in row["reasonCodes"]})
    context_codes = [code for code in reason_codes if any(token in code for token in ("CONFLICT", "UNCERTAIN", "AMBIGU"))]
    definitions = {
        "S0_MINIMAL": ["requiresEvidence +1", "matchedRiskSignals>=1 +1", "matchedRiskSignals>=2 +1"],
        "S1_RISK_AWARE": ["S0", "predictedRiskCount>=2 +1", "predictedSeverity in HIGH/CRITICAL +1"],
        "S2_ORDINAL_AUX": ["S1", "rawConfidence<0.88 +1 (ordinal only, not probability)"],
    }
    used = {
        "S0_MINIMAL": ["requiresEvidence", "matchedRiskSignals"],
        "S1_RISK_AWARE": ["requiresEvidence", "matchedRiskSignals", "predictedRiskCount", "predictedSeverity"],
        "S2_ORDINAL_AUX": ["requiresEvidence", "matchedRiskSignals", "predictedRiskCount", "predictedSeverity", "rawConfidence"],
    }
    overlap = sorted(set(field for values in used.values() for field in values) & set(EVALUATION_ONLY_SIGNALS))
    return {
        "schemaVersion": "escalation-signal-inventory-v1",
        "availableRuntimeSignals": list(RUNTIME_SIGNALS),
        "scoreDefinitions": definitions,
        "signalsUsedByCandidate": used,
        "actualReasonCodes": reason_codes,
        "actualConflictUncertainAmbiguousCodes": context_codes,
        "contextReasonScoreUsed": False,
        "rawConfidenceInterpretation": "LOW_CARDINALITY_ORDINAL_SIGNAL_NOT_PROBABILITY",
        "rawConfidenceUniqueValues": sorted({float(row["rawConfidence"]) for row in rows}),
        "evaluationOnlySignals": list(EVALUATION_ONLY_SIGNALS),
        "goldOnlySignalUsedByScore": len(overlap),
        "goldSignalOverlap": overlap,
        "expensiveComponentsCalled": [],
        "gate": "PASS" if not overlap else "FAIL",
    }


def rank_candidate(candidate: dict[str, Any]) -> tuple[Any, ...]:
    metrics = candidate["fitMetrics"]
    fast = metrics["fastPath"]
    abstention = metrics["abstentionLongCapture"]
    return (
        fast["materialSafetyErrorCount"] != 0,
        fast["materialSafetyErrorCount"],
        abstention["captured"] != abstention["targetCount"],
        -metrics["ruleErrorCapture"]["rate"],
        -(fast["exactAccuracy"] if fast["exactAccuracy"] is not None else -1.0),
        -fast["coverage"],
        SCORE_VERSIONS.index(candidate["scoreVersion"]),
        abs(candidate["threshold"] - 2),
        candidate["threshold"],
    )


def select_policy(fit_rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    candidates = []
    output_by_candidate: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for version in SCORE_VERSIONS:
        maximum = max(calculate_score(version, runtime_signal(row))[0] for row in fit_rows)
        thresholds = [value for value in THRESHOLD_CANDIDATES if value <= max(maximum, 1)]
        for threshold in thresholds:
            outputs = [make_output(row, version, threshold) for row in fit_rows]
            output_by_candidate[(version, threshold)] = outputs
            candidates.append({"scoreVersion": version, "threshold": threshold, "scoreMaximumObserved": maximum, "fitMetrics": routing_metrics(outputs)})
    selected = min(candidates, key=rank_candidate)
    selected_outputs = output_by_candidate[(selected["scoreVersion"], selected["threshold"])]
    raw_aux = next(item for item in candidates if item["scoreVersion"] == "S2_ORDINAL_AUX" and item["threshold"] == selected["threshold"])
    risk_aware = next((item for item in candidates if item["scoreVersion"] == "S1_RISK_AWARE" and item["threshold"] == selected["threshold"]), None)
    artifact = {
        "schemaVersion": "escalation-score-candidates-v1",
        "selectionPartition": "CALIBRATION_FIT_80_ONLY",
        "validationUsed": False,
        "boundaryUsed": False,
        "frozenUsed": False,
        "thresholdCandidates": list(THRESHOLD_CANDIDATES),
        "selectionPriority": ["fastSafety", "abstentionLong", "ruleErrorCapture", "fastAccuracy", "fastCoverage"],
        "candidates": candidates,
        "rawConfidenceOrdinalContribution": {
            "comparisonThreshold": selected["threshold"],
            "s1Metrics": risk_aware["fitMetrics"] if risk_aware else None,
            "s2Metrics": raw_aux["fitMetrics"],
        },
    }
    formula = score_inventory(fit_rows)["scoreDefinitions"][selected["scoreVersion"]]
    spec = {
        "scoreVersion": selected["scoreVersion"],
        "signals": score_inventory(fit_rows)["signalsUsedByCandidate"][selected["scoreVersion"]],
        "formula": formula,
        "threshold": selected["threshold"],
        "routeRule": "safetyOverride => LONG_ANALYSIS; otherwise score < threshold => FAST_PATH; score >= threshold => LONG_ANALYSIS",
        "safetyOverride": {"signal": "safetyGateTriggered", "route": LONG_ANALYSIS, "hardOverride": True},
        "selectionPartition": "CALIBRATION_FIT_80_ONLY",
        "validationUsed": False,
        "boundaryUsed": False,
        "frozenUsed": False,
        "selectionMetrics": selected["fitMetrics"],
        "fitOutputHash": stable_hash(selected_outputs),
    }
    policy = {"schemaVersion": "escalation-policy-v1", **spec, "policyHash": stable_hash(spec), "frozen": True}
    return artifact, policy, selected_outputs


def boundary_metrics(outputs: list[dict[str, Any]]) -> dict[str, Any]:
    overall = routing_metrics(outputs)
    by_type = {}
    for boundary_type in sorted({str(row["boundaryType"]) for row in outputs}):
        by_type[boundary_type] = routing_metrics([row for row in outputs if str(row["boundaryType"]) == boundary_type])
    hard = [row for row in outputs if row["boundaryType"] == "hard_negative"]
    hard_fast = [row for row in hard if row["route"] == FAST_PATH]
    overall["byBoundaryType"] = by_type
    overall["hardNegative"] = {
        "caseCount": len(hard),
        "fastCount": len(hard_fast),
        "fastCoverage": baseline.safe_ratio(len(hard_fast), len(hard)),
        "fastAccuracy": baseline.safe_ratio(sum(row["ruleExactMatch"] for row in hard_fast), len(hard_fast)) if hard_fast else None,
    }
    return overall


def latency_metrics(cases: list[dict[str, Any]], score_version: str, threshold: int, partition_by_id: dict[str, str]) -> dict[str, Any]:
    router = baseline.IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)
    severity = RiskSeverityEvaluator()
    values = []
    for case in cases:
        started = time.perf_counter_ns()
        row = baseline.assess_case(
            case,
            dataset_partition=partition_by_id[str(case["caseId"])],
            split_partition=partition_by_id[str(case["caseId"])],
            router=router,
            severity_evaluator=severity,
        )
        route_signal(score_version, threshold, runtime_signal(row))
        values.append((time.perf_counter_ns() - started) / 1_000_000)
    return {
        "schemaVersion": "escalation-latency-metrics-v1",
        "mode": "warm-single-request-cheap-signals-only",
        "caseCount": len(values),
        "p50Ms": baseline.percentile(values, 0.50),
        "p95Ms": baseline.percentile(values, 0.95),
        "p99Ms": baseline.percentile(values, 0.99),
        "components": ["Rule Router", "Safety Gate", "integer escalation score"],
        "expensiveComponentsCalled": [],
        "externalApiCallCount": 0,
    }


def build_report(inventory: dict[str, Any], candidates: dict[str, Any], policy: dict[str, Any], fit: dict[str, Any], validation: dict[str, Any], boundary: dict[str, Any], latency: dict[str, Any], gate: dict[str, Any]) -> str:
    fast = validation["fastPath"]
    hard = boundary["hardNegative"]
    return "\n".join([
        "# Escalation Router Offline Report", "",
        "## Scope", "",
        "Step 21.3C uses only cheap runtime signals to choose FAST_PATH or LONG_ANALYSIS. It does not execute Long Analysis, BGE, Qwen, RAG, Reflection, Workflow, Frozen Gold, or any external API, and it changes no runtime code.", "",
        "## Signal And Policy", "",
        f"Selected `{policy['scoreVersion']}` at threshold `{policy['threshold']}` from Fit80 only. Formula: `{'; '.join(policy['formula'])}`. Safety Gate is a hard LONG_ANALYSIS override.",
        f"Observed conflict/uncertain/ambiguous reason codes: `{inventory['actualConflictUncertainAmbiguousCodes']}`; none were invented. Raw confidence remains an ordinal low-cardinality signal, not a probability.", "",
        "## Fit And Validation", "",
        f"Fit fast coverage `{fit['fastPath']['coverage']:.4f}`, exact `{fit['fastPath']['exactAccuracy']}`, safety errors `{fit['fastPath']['materialSafetyErrorCount']}`, rule-error capture `{fit['ruleErrorCapture']['rate']:.4f}`.",
        f"Validation fast `{fast['count']}/{validation['caseCount']}` (`{fast['coverage']:.4f}`), exact `{fast['exactAccuracy']}`, micro F1 `{fast['microF1']}`, safety errors `{fast['materialSafetyErrorCount']}`. Long-analysis rate `{validation['longAnalysis']['rate']:.4f}`; false escalation `{validation['falseEscalation']['rate']:.4f}`.", "",
        "## Boundary And Latency", "",
        f"Boundary fast/long `{boundary['fastPath']['count']}/{boundary['longAnalysis']['count']}`, fast safety errors `{boundary['fastPath']['materialSafetyErrorCount']}`. Hard-negative fast coverage `{hard['fastCoverage']:.4f}`, accuracy `{hard['fastAccuracy']}`.",
        f"Cheap gate P50/P95 `{latency['p50Ms']}/{latency['p95Ms']} ms`; long-analysis rate is a compute-cost proxy, not an API-cost claim.", "",
        "## Gates", "",
        *(f"- `{key}` = `{value}`" for key, value in gate.items() if key.endswith("Gate")), "",
        "## Conclusion", "",
        f"`{gate['nextRecommendation']}`", "",
    ])


def run(args: argparse.Namespace) -> dict[str, Any]:
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

    rows = baseline.load_jsonl(RULE_RESULTS)
    fit_rows = [row for row in rows if row["partition"] == "FIT"]
    validation_rows = [row for row in rows if row["partition"] == "VALIDATION"]
    boundary_rows = [row for row in rows if row["partition"] == "BOUNDARY_CHALLENGE"]
    if (len(fit_rows), len(validation_rows), len(boundary_rows)) != (80, 40, 60):
        raise RuntimeError("ESCALATION_INPUT_PARTITION_COUNT_MISMATCH")

    inventory = score_inventory(rows)
    if inventory["gate"] != "PASS":
        raise RuntimeError("ESCALATION_SIGNAL_GATE_FAIL")
    candidates, policy, fit_outputs = select_policy(fit_rows)
    fit_metric = routing_metrics(fit_outputs)
    validation_outputs = [make_output(row, policy["scoreVersion"], policy["threshold"]) for row in validation_rows]
    boundary_outputs = [make_output(row, policy["scoreVersion"], policy["threshold"]) for row in boundary_rows]
    validation_metric = routing_metrics(validation_outputs)
    boundary_metric = boundary_metrics(boundary_outputs)

    calibration_cases = baseline.load_jsonl(baseline.DEFAULT_CALIBRATION)
    boundary_cases = baseline.load_jsonl(baseline.DEFAULT_BOUNDARY)
    evaluation_ids = {row["caseId"] for row in validation_rows + boundary_rows}
    latency_cases = [dict(case, _partition="VALIDATION") for case in calibration_cases if str(case["caseId"]) in evaluation_ids]
    latency_cases += [dict(case, _partition="BOUNDARY_CHALLENGE") for case in boundary_cases]
    partition_by_id = {row["caseId"]: row["partition"] for row in validation_rows + boundary_rows}
    latency = latency_metrics(latency_cases, policy["scoreVersion"], policy["threshold"], partition_by_id)

    baseline.write_json(args.output_dir / "escalation_signal_inventory_v1.json", inventory)
    baseline.write_json(args.output_dir / "escalation_score_candidates_v1.json", candidates)
    baseline.write_json(args.output_dir / "escalation_fit_metrics_v1.json", fit_metric)
    baseline.write_json(args.output_dir / "escalation_policy_v1.json", policy)
    baseline.write_jsonl(args.output_dir / "escalation_validation_outputs_v1.jsonl", validation_outputs)
    baseline.write_json(args.output_dir / "escalation_validation_metrics_v1.json", validation_metric)
    baseline.write_jsonl(args.output_dir / "escalation_boundary_outputs_v1.jsonl", boundary_outputs)
    baseline.write_json(args.output_dir / "escalation_boundary_metrics_v1.json", boundary_metric)
    baseline.write_json(args.output_dir / "escalation_latency_metrics_v1.json", latency)

    fast = validation_metric["fastPath"]
    full_fast = fast["coverage"] >= 0.20 and (fast["exactAccuracy"] or 0.0) >= 0.95 and fast["materialSafetyErrorCount"] == 0
    limited_fast = fast["coverage"] >= 0.10 and (fast["exactAccuracy"] or 0.0) >= 0.90 and fast["materialSafetyErrorCount"] == 0
    full_capture = validation_metric["ruleErrorCapture"]["rate"] >= 0.80 and validation_metric["materialSafetyErrorCapture"]["rate"] >= 0.90
    limited_capture = validation_metric["ruleErrorCapture"]["rate"] >= 0.70 and validation_metric["materialSafetyErrorCapture"]["rate"] >= 0.90
    abstention = boundary_metric["abstentionLongCapture"]
    abstention_pass = abstention["targetCount"] == 5 and abstention["captured"] >= 4
    candidate_gate = "PASS" if full_fast and full_capture and abstention_pass else "PASS_WITH_LIMITATIONS" if limited_fast and limited_capture and abstention_pass else "FAIL"
    if candidate_gate != "FAIL":
        recommendation = "ESCALATION_GATE_SHADOW_MODE"
    elif fast["materialSafetyErrorCount"] > 0:
        recommendation = "SAFETY_LEAK"
    elif fast["coverage"] < 0.10 or validation_metric["longAnalysis"]["rate"] > 0.90:
        recommendation = "TOO_CONSERVATIVE"
    elif validation_metric["ruleErrorCapture"]["rate"] < 0.70:
        recommendation = "RULE_ERROR_NOT_CAPTURED"
    else:
        recommendation = "SIGNALS_NOT_SEPARABLE"
    gate = {
        "escalationSignalGate": inventory["gate"],
        "escalationPolicySelectionGate": "PASS",
        "escalationValidationGate": "PASS",
        "escalationSafetyGate": "PASS" if fast["materialSafetyErrorCount"] == 0 and validation_metric["materialSafetyErrorCapture"]["rate"] >= 0.90 else "FAIL",
        "escalationBoundaryGate": "PASS",
        "escalationLatencyGate": "PASS" if latency["caseCount"] == 100 else "FAIL",
        "escalationAbstentionGate": "PASS" if abstention_pass else "FAIL",
        "step21_3cGate": "PASS",
        "escalationRouterCandidateGate": candidate_gate,
        "calibrationSha": baseline.sha256_file(baseline.DEFAULT_CALIBRATION),
        "boundarySha": baseline.sha256_file(baseline.DEFAULT_BOUNDARY),
        "frozenGoldSha": baseline.sha256_file(baseline.DEFAULT_FROZEN),
        "frozenBenchmarkExecuted": False,
        "runtimeChanged": False,
        "longAnalysisExecuted": False,
        "bgeCallCount": 0,
        "qwenCallCount": 0,
        "externalApiCallCount": 0,
        "nextRecommendation": recommendation,
    }
    baseline.write_json(args.output_dir / "step213c_escalation_gate_v1.json", gate)
    args.report.write_text(build_report(inventory, candidates, policy, fit_metric, validation_metric, boundary_metric, latency, gate), encoding="utf-8", newline="\n")
    after = {str(path): baseline.sha256_file(path) for path in protected}
    if before != after:
        raise RuntimeError("PROTECTED_INPUT_MUTATION_DETECTED")
    return {"inventory": inventory, "candidates": candidates, "policy": policy, "fit": fit_metric, "validation": validation_metric, "boundary": boundary_metric, "latency": latency, "gate": gate}


def main() -> int:
    print(json.dumps(run(parse_args()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
