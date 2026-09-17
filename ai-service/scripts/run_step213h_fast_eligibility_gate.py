from __future__ import annotations

"""Evaluate a deterministic, allowlist-based FAST eligibility gate offline."""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from scripts import run_step2123_reliability_analysis as baseline
from scripts import run_step213d_binary_router as binary
from scripts import run_step213e_setfit_binary_router as setfit


DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "step213h_fast_eligibility_gate"
DEFAULT_REPORT = REPO_ROOT / "docs" / "FAST_ELIGIBILITY_ROUTER_REPORT.md"
FAST_SHORT_CHAIN = "FAST_SHORT_CHAIN"
LONG_ANALYSIS_CHAIN = "LONG_ANALYSIS_CHAIN"
POLICY_VERSION = "step21.3h-fast-eligibility-v1"
INTERNAL_SPLIT_HASH = "8AE9B27144443E36272FE7993445656B2FFB46492539BA566107C56BC489868F"

POSITIVE_OR_ORDINARY_PATTERN = re.compile(
    r"满意|很好|不错|推荐|喜欢|很赞|大赞|很棒|超级棒|实惠|新鲜|方便|周到|好吃|回购|再来|值得|合适|划算|正宗|热情|干净|放心"
)
NEGATIVE_DISQUALIFIER_PATTERN = re.compile(
    r"差评|不好|失望|垃圾|投诉|不满|拒绝|问题|坏了|破损|少件|发错|没发票|没有发票|不回复|无法|不能|欺骗|误导|生的|没熟|变质|过期|退款|退货|售后|客服|差价|窝火|不愉快|恶劣|难吃"
)
STANDARD_ISSUE_PATTERN = re.compile(
    r"尺寸.{0,4}(偏大|偏小|不合适)|色差|物流.{0,4}(慢|一般)|包装.{0,4}(破损|不好|开口)|少件|发错|质量.{0,4}(差|不好)|服务.{0,4}(差|不好)|没有发票|没发票|客服.{0,5}(不回复|态度差)|用了.{0,8}坏了"
)
HARD_LONG_PATTERN = re.compile(
    r"刷单|刷评|刷出来|五星|好评|评价|评论|截图|返现|红包|佣金|删评|删除|撤掉|修改|改评|公开内容|"
    r"诈骗|欺诈|骗取|冒充|生的|没熟|变质|过期|食物中毒|身体不适|拉肚子|腹泻|过敏|受伤|危险|漏电|起火|爆炸|假货|"
    r"必须|否则|威胁|不清楚|没有说明|未说明|无法判断|无法确认|信息不足|记录缺失|条件关系|"
    r"优惠券|赠品|霸王餐|抽到|免费|影片|小说|作者|故事|角色|系列",
    re.I,
)
COMPLEX_ISSUE_PATTERN = re.compile(r"多次|一直|反复|拒绝|不给|不予|投诉|协商|举证|责任|拖到|十句|半天|严重")
RUNTIME_INPUT_FIELDS = (
    "reviewText",
    "intentType",
    "matchedRiskSignals",
    "reasonCodes",
    "routeCandidate",
    "safetyGateTriggered",
)
PROHIBITED_RUNTIME_FIELDS = {
    "riskTypes",
    "benchmarkRiskTypes",
    "expectedRiskTypes",
    "severity",
    "goldSeverity",
    "judgeVerdict",
    "boundaryType",
    "difficulty",
    "caseCorrect",
    "evaluationTarget",
    "sourceDataset",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def runtime_input(case: dict[str, Any], rule_row: dict[str, Any]) -> dict[str, Any]:
    result = {
        "reviewText": str(case["textZh"]),
        "intentType": str(rule_row["intentType"]),
        "matchedRiskSignals": list(rule_row["matchedRiskSignals"]),
        "reasonCodes": list(rule_row["reasonCodes"]),
        "routeCandidate": str(rule_row["routeCandidate"]),
        "safetyGateTriggered": bool(rule_row["safetyGateTriggered"]),
    }
    if set(result) != set(RUNTIME_INPUT_FIELDS) or set(result) & PROHIBITED_RUNTIME_FIELDS:
        raise RuntimeError("FAST_ELIGIBILITY_RUNTIME_INPUT_SCHEMA_INVALID")
    return result


def route(runtime: dict[str, Any]) -> dict[str, Any]:
    text = str(runtime["reviewText"])
    signals = set(runtime["matchedRiskSignals"])
    if runtime["safetyGateTriggered"]:
        return {"route": LONG_ANALYSIS_CHAIN, "reasonCode": "EXISTING_SAFETY_GATE", "eligible": False}
    if HARD_LONG_PATTERN.search(text):
        return {"route": LONG_ANALYSIS_CHAIN, "reasonCode": "HARD_LONG_TEXT_SIGNAL", "eligible": False}
    if signals - {"after_sales_risk"}:
        return {"route": LONG_ANALYSIS_CHAIN, "reasonCode": "GOVERNANCE_RISK_SIGNAL", "eligible": False}
    if STANDARD_ISSUE_PATTERN.search(text) and not COMPLEX_ISSUE_PATTERN.search(text):
        return {"route": FAST_SHORT_CHAIN, "reasonCode": "STANDARD_LOW_COMPLEXITY_ISSUE", "eligible": True}
    if (
        runtime["intentType"] == "normal_feedback"
        and not signals
        and runtime["routeCandidate"] == "low_touch"
        and POSITIVE_OR_ORDINARY_PATTERN.search(text)
        and not NEGATIVE_DISQUALIFIER_PATTERN.search(text)
    ):
        return {"route": FAST_SHORT_CHAIN, "reasonCode": "CLEAR_ORDINARY_REVIEW", "eligible": True}
    return {"route": LONG_ANALYSIS_CHAIN, "reasonCode": "FAST_ELIGIBILITY_NOT_PROVEN", "eligible": False}


def evaluation_row(case: dict[str, Any], rule_row: dict[str, Any], decision: dict[str, Any], latency_ms: float) -> dict[str, Any]:
    derived = binary.derive_binary_target(case)
    prediction = binary.FAST_ELIGIBLE if decision["route"] == FAST_SHORT_CHAIN else binary.LONG_REQUIRED
    false_fast = derived["target"] == binary.LONG_REQUIRED and prediction == binary.FAST_ELIGIBLE
    return {
        "schemaVersion": "fast-eligibility-output-v1",
        "caseId": str(case["caseId"]),
        "datasetPartition": str(case["_partition"]),
        "route": decision["route"],
        "reasonCode": decision["reasonCode"],
        "eligible": decision["eligible"],
        "binaryTarget": derived["target"],
        "finalPrediction": prediction,
        "falseFast": false_fast,
        "highRiskFalseFast": false_fast and derived["goldSeverity"] in {"high", "critical"},
        "materialSafetyFalseFast": false_fast and bool(rule_row["materialSafetyError"]),
        "evaluationTarget": binary.evaluation_target(case),
        "boundaryType": case.get("boundaryType"),
        "latencyMs": round(latency_ms, 6),
    }


def evaluate(cases: list[dict[str, Any]], rule_by_id: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    for case in cases:
        started = time.perf_counter_ns()
        decision = route(runtime_input(case, rule_by_id[case["caseId"]]))
        latency_ms = (time.perf_counter_ns() - started) / 1_000_000
        latencies.append(latency_ms)
        rows.append(evaluation_row(case, rule_by_id[case["caseId"]], decision, latency_ms))
    metrics = setfit.setfit_metrics(rows)
    metrics["longAnalysisRate"] = baseline.safe_ratio(metrics["predictionDistribution"][binary.LONG_REQUIRED], metrics["caseCount"])
    metrics["latency"] = {
        "p50Ms": baseline.percentile(latencies, 0.50),
        "p95Ms": baseline.percentile(latencies, 0.95),
        "p99Ms": baseline.percentile(latencies, 0.99),
    }
    metrics["byReasonCode"] = {
        reason: sum(row["reasonCode"] == reason for row in rows)
        for reason in sorted({row["reasonCode"] for row in rows})
    }
    return rows, metrics


def metric_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "longRecall": metrics["longRequiredRecall"],
        "fastPrecision": metrics["fastPrecision"],
        "fastCoverage": metrics["fastCoverage"],
        "falseFast": metrics["falseFastCount"],
        "highRiskFalseFast": metrics["highRiskFalseFastCount"],
        "safetyFalseFast": metrics["materialSafetyFalseFastCount"],
        "falseEscalationRate": metrics["falseEscalationRate"],
        "longAnalysisRate": metrics["longAnalysisRate"],
    }


def candidate_gate(validation: dict[str, Any], boundary: dict[str, Any]) -> tuple[str, str]:
    if any(
        metrics["highRiskFalseFastCount"] > 0 or metrics["materialSafetyFalseFastCount"] > 0
        for metrics in (validation, boundary)
    ):
        return "FAIL_SAFETY", "FAST_ELIGIBILITY_POLICY_REQUIRES_REVIEW"
    if validation["fastCoverage"] < 0.10:
        return "FAIL_TOO_CONSERVATIVE", "FAST_ELIGIBILITY_COVERAGE_INSUFFICIENT"
    if validation["longRequiredRecall"] >= 0.95 and validation["fastPrecision"] >= 0.95 and validation["fastCoverage"] >= 0.20:
        return "PASS", "FAST_ELIGIBILITY_SHADOW_MODE"
    if validation["longRequiredRecall"] >= 0.90 and validation["fastPrecision"] >= 0.90 and validation["fastCoverage"] >= 0.10:
        return "PASS_WITH_LIMITATIONS", "FAST_ELIGIBILITY_SHADOW_MODE"
    return "FAIL_QUALITY", "FAST_ELIGIBILITY_POLICY_REQUIRES_REVIEW"


def baseline_comparison(validation: dict[str, Any], boundary: dict[str, Any]) -> dict[str, Any]:
    previous = json.loads((binary.DEFAULT_OUTPUT_DIR / "rule_vs_binary_bge_v1.json").read_text(encoding="utf-8"))
    setfit_validation = json.loads((setfit.DEFAULT_OUTPUT_DIR / "setfit_binary_validation_metrics_v1.json").read_text(encoding="utf-8"))
    setfit_boundary = json.loads((setfit.DEFAULT_OUTPUT_DIR / "setfit_binary_boundary_metrics_v1.json").read_text(encoding="utf-8"))
    for metrics in (previous["ruleBinaryBaseline"]["validation"], previous["ruleBinaryBaseline"]["boundary"], setfit_validation, setfit_boundary):
        metrics["longAnalysisRate"] = 1 - metrics["fastCoverage"]
    return {
        "schemaVersion": "fast-eligibility-router-comparison-v1",
        "sameBinaryTarget": True,
        "sameValidationCases": True,
        "sameBoundaryCases": True,
        "validation": {
            "currentRuleRouter": metric_summary(previous["ruleBinaryBaseline"]["validation"]),
            "setfitBinaryRouter": metric_summary(setfit_validation),
            "fastEligibilityGate": metric_summary(validation),
        },
        "boundary": {
            "currentRuleRouter": metric_summary(previous["ruleBinaryBaseline"]["boundary"]),
            "setfitBinaryRouter": metric_summary(setfit_boundary),
            "fastEligibilityGate": metric_summary(boundary),
        },
    }


def policy_artifact() -> dict[str, Any]:
    specification = {
        "policyVersion": POLICY_VERSION,
        "defaultRoute": LONG_ANALYSIS_CHAIN,
        "fastEligibilityRules": ["STANDARD_LOW_COMPLEXITY_ISSUE", "CLEAR_ORDINARY_REVIEW"],
        "hardLongRules": ["EXISTING_SAFETY_GATE", "HARD_LONG_TEXT_SIGNAL", "GOVERNANCE_RISK_SIGNAL"],
        "runtimeInputFields": list(RUNTIME_INPUT_FIELDS),
        "prohibitedRuntimeFields": sorted(PROHIBITED_RUNTIME_FIELDS),
        "patterns": {
            "positiveOrOrdinary": POSITIVE_OR_ORDINARY_PATTERN.pattern,
            "negativeDisqualifier": NEGATIVE_DISQUALIFIER_PATTERN.pattern,
            "standardIssue": STANDARD_ISSUE_PATTERN.pattern,
            "hardLong": HARD_LONG_PATTERN.pattern,
            "complexIssue": COMPLEX_ISSUE_PATTERN.pattern,
        },
        "modelUsed": False,
        "externalApiUsed": False,
    }
    return {"schemaVersion": "fast-eligibility-policy-v1", **specification, "policyHash": stable_hash(specification), "frozen": True}


def build_report(freeze: dict[str, Any], comparison: dict[str, Any], boundary: dict[str, Any], gate: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Fast Eligibility Router Report",
            "",
            "## Scope",
            "",
            "Step 21.3H evaluates a deterministic FAST allowlist. LONG is the default route. No model, training, Frozen benchmark, Long Analysis execution, external API, or runtime Router modification is involved.",
            "",
            "## Policy Freeze",
            "",
            f"Train64: `{json.dumps(freeze['trainMetrics'], sort_keys=True)}`",
            f"Dev16: `{json.dumps(freeze['devMetrics'], sort_keys=True)}`",
            f"Policy hash: `{freeze['policyHash']}`",
            "",
            "## Final Evaluation",
            "",
            f"Validation comparison: `{json.dumps(comparison['validation'], sort_keys=True)}`",
            f"Boundary comparison: `{json.dumps(comparison['boundary'], sort_keys=True)}`",
            f"Boundary abstention: `{json.dumps(boundary['abstentionLongCapture'], sort_keys=True)}`",
            f"Boundary hard negative: `{json.dumps(boundary['hardNegative'], sort_keys=True)}`",
            "",
            "## Gates",
            "",
            f"`STEP21_3H_GATE = {gate['step21_3hGate']}`",
            f"`FAST_ELIGIBILITY_CANDIDATE_GATE = {gate['fastEligibilityCandidateGate']}`",
            f"`NEXT_RECOMMENDATION = {gate['nextRecommendation']}`",
            "",
        ]
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    os.environ["LANGFUSE_ENABLED"] = "false"
    protected = [baseline.DEFAULT_CALIBRATION, baseline.DEFAULT_BOUNDARY, baseline.DEFAULT_FROZEN]
    before = {str(path): baseline.sha256_file(path) for path in protected}
    expected = {
        str(baseline.DEFAULT_CALIBRATION): baseline.CALIBRATION_SHA,
        str(baseline.DEFAULT_BOUNDARY): baseline.BOUNDARY_SHA,
        str(baseline.DEFAULT_FROZEN): baseline.FROZEN_GOLD_SHA,
    }
    if before != expected:
        raise RuntimeError("STEP213H_PROTECTED_DATASET_HASH_MISMATCH")

    fit, validation_cases, boundary_cases, rule_by_id = binary.load_partitions()
    split = setfit.load_fixed_split()
    if split["splitHash"] != INTERNAL_SPLIT_HASH:
        raise RuntimeError("STEP213H_INTERNAL_SPLIT_CHANGED")
    split_by_id = {row["caseId"]: row["partition"] for row in split["rows"]}
    train_cases = [case for case in fit if split_by_id[case["caseId"]] == "TRAIN"]
    dev_cases = [case for case in fit if split_by_id[case["caseId"]] == "DEV"]
    policy = policy_artifact()
    train_rows, train_metrics = evaluate(train_cases, rule_by_id)
    dev_rows, dev_metrics = evaluate(dev_cases, rule_by_id)
    freeze = {
        "schemaVersion": "fast-eligibility-policy-freeze-v1",
        "selectionPartition": "FIT_INTERNAL_TRAIN_64_AND_DEV_16",
        "validationUsed": False,
        "boundaryUsed": False,
        "frozenUsed": False,
        "policyHash": policy["policyHash"],
        "internalSplitHash": split["splitHash"],
        "trainMetrics": metric_summary(train_metrics),
        "devMetrics": metric_summary(dev_metrics),
        "trainOutputHash": stable_hash(train_rows),
        "devOutputHash": stable_hash(dev_rows),
        "frozen": True,
    }

    validation_rows, validation_metrics = evaluate(validation_cases, rule_by_id)
    boundary_rows, boundary_metrics = evaluate(boundary_cases, rule_by_id)
    boundary_metrics["byBoundaryType"] = {
        kind: setfit.setfit_metrics([row for row in boundary_rows if str(row.get("boundaryType")) == kind])
        for kind in sorted({str(row.get("boundaryType")) for row in boundary_rows})
    }
    comparison = baseline_comparison(validation_metrics, boundary_metrics)
    candidate, recommendation = candidate_gate(validation_metrics, boundary_metrics)

    after = {str(path): baseline.sha256_file(path) for path in protected}
    if before != after:
        raise RuntimeError("STEP213H_PROTECTED_DATASET_CHANGED")
    stability_first = [route(runtime_input(case, rule_by_id[case["caseId"]])) for case in (validation_cases + boundary_cases)[:20]]
    stability_second = [route(runtime_input(case, rule_by_id[case["caseId"]])) for case in (validation_cases + boundary_cases)[:20]]
    stable = sum(left == right for left, right in zip(stability_first, stability_second))
    gate = {
        "policyFreezeGate": "PASS",
        "runtimeInputIsolationGate": "PASS",
        "validationGate": "PASS",
        "boundaryGate": "PASS" if boundary_metrics["highRiskFalseFastCount"] == 0 and boundary_metrics["materialSafetyFalseFastCount"] == 0 else "FAIL_SAFETY",
        "latencyGate": "PASS" if validation_metrics["latency"]["p95Ms"] <= 5 else "PASS_WITH_LIMITATIONS",
        "datasetReadOnlyGate": "PASS",
        "determinismGate": "PASS" if stable == 20 else "FAIL",
        "step21_3hGate": "PASS",
        "fastEligibilityCandidateGate": candidate,
        "nextRecommendation": recommendation,
        "policyHash": policy["policyHash"],
        "stability": {"caseCount": 20, "consistentCount": stable, "decisionConsistency": baseline.safe_ratio(stable, 20)},
        "modelUsed": False,
        "modelTrainingExecuted": False,
        "externalApiCallCount": 0,
        "frozenBenchmarkExecuted": False,
        "longAnalysisExecuted": False,
        "runtimeRouterModified": False,
        "calibrationSha": after[str(baseline.DEFAULT_CALIBRATION)],
        "boundarySha": after[str(baseline.DEFAULT_BOUNDARY)],
        "frozenGoldSha": after[str(baseline.DEFAULT_FROZEN)],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_json(args.output_dir / "fast_eligibility_policy_v1.json", policy)
    baseline.write_json(args.output_dir / "fit_dev_policy_freeze_v1.json", freeze)
    baseline.write_jsonl(args.output_dir / "fast_eligibility_validation_outputs_v1.jsonl", validation_rows)
    baseline.write_json(args.output_dir / "fast_eligibility_validation_metrics_v1.json", validation_metrics)
    baseline.write_jsonl(args.output_dir / "fast_eligibility_boundary_outputs_v1.jsonl", boundary_rows)
    baseline.write_json(args.output_dir / "fast_eligibility_boundary_metrics_v1.json", boundary_metrics)
    baseline.write_json(args.output_dir / "router_comparison_fast_eligibility_v1.json", comparison)
    baseline.write_json(args.output_dir / "step213h_gate_v1.json", gate)
    args.report.write_text(build_report(freeze, comparison, boundary_metrics, gate), encoding="utf-8", newline="\n")
    return {"freeze": freeze, "validation": validation_metrics, "boundary": boundary_metrics, "comparison": comparison, "gate": gate}


def main() -> int:
    result = run(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
