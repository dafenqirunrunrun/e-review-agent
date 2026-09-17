from __future__ import annotations

"""Evaluate DuoGuard plus isolated business rules as an offline escalation router."""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from scripts import run_step2123_reliability_analysis as baseline
from scripts import run_step213d_binary_router as binary
from scripts import run_step213e_setfit_binary_router as setfit


DEFAULT_MODEL_DIR = ROOT.parents[1] / "models" / "DuoGuard-0.5B"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "step213g_safety_guard_router"
DEFAULT_REPORT = REPO_ROOT / "docs" / "SAFETY_GUARD_ROUTER_REPORT.md"
MODEL_ID = "DuoGuard/DuoGuard-0.5B"
MODEL_REVISION = "44396C3576FDD5F844C64615489CDBB5B3B3F3CE"
TOKENIZER_ID = "Qwen/Qwen2.5-0.5B"
TOKENIZER_REVISION = "060DB6499F32FAF8B98477B0A26969EF7D8B9987"
MODEL_LICENSE = "Apache-2.0"
UNSAFE_THRESHOLD = 0.5
MAX_LENGTH = 512
FAST_SHORT_CHAIN = "FAST_SHORT_CHAIN"
LONG_ANALYSIS_CHAIN = "LONG_ANALYSIS_CHAIN"
SAFETY_CATEGORIES = (
    "violent_crimes",
    "non_violent_crimes",
    "sex_related_crimes",
    "child_sexual_exploitation",
    "specialized_advice",
    "privacy",
    "intellectual_property",
    "indiscriminate_weapons",
    "hate",
    "suicide_and_self_harm",
    "sexual_content",
    "jailbreak_prompts",
)
BUSINESS_RISK_PATTERNS: dict[str, tuple[str, ...]] = {
    "paid_review": (
        r"好评.{0,6}(返现|红包|佣金|补偿)",
        r"(返现|红包|佣金|补偿).{0,8}(好评|评价|五星|评分)",
        r"paid\s+review|incentivi[sz]ed\s+review",
    ),
    "rating_manipulation": (
        r"刷单|刷评|五星截图|五星好评|评分操纵|集中打分",
        r"rating\s+manipulation|manipulat(?:e|ing)\s+(?:the\s+)?rating",
    ),
    "review_suppression": (
        r"删除差评|删掉差评|撤掉差评|删评|屏蔽评价|压制差评|不删.{0,5}(不给|不予)",
        r"review\s+suppression|remove\s+(?:the\s+)?negative\s+review",
    ),
    "fake_review": (
        r"虚假评价|虚构评价|编造评价|虚构体验|代写评价|刷单|刷评",
        r"fake\s+(?:review|engagement)|fabricated\s+review",
    ),
    "fraud": (r"诈骗|欺诈|骗取|冒充|fraud|scam",),
}
AFTER_SALES_PATTERN = re.compile(r"退款|退货|换货|售后|维修|赔付|补偿|客服|物流|破损", re.I)
COMPLEXITY_PATTERN = re.compile(r"多次|一直|反复|拒绝|不给|无法|不能|投诉|协商|举证|责任|记录缺失|关系无法确认", re.I)
ABSTENTION_PATTERN = re.compile(r"不清楚|没有说明|未说明|无法判断|无法确认|信息不足|上下文.{0,4}(不足|缺失|无法)|记录缺失", re.I)
RUNTIME_INPUT_FIELDS = (
    "reviewText",
    "matchedRiskSignals",
    "reasonCodes",
    "intentType",
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
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    return parser.parse_args()


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def runtime_input(case: dict[str, Any], rule_row: dict[str, Any]) -> dict[str, Any]:
    result = {
        "reviewText": str(case["textZh"]),
        "matchedRiskSignals": list(rule_row["matchedRiskSignals"]),
        "reasonCodes": list(rule_row["reasonCodes"]),
        "intentType": str(rule_row["intentType"]),
        "safetyGateTriggered": bool(rule_row["safetyGateTriggered"]),
    }
    if set(result) != set(RUNTIME_INPUT_FIELDS) or set(result) & PROHIBITED_RUNTIME_FIELDS:
        raise RuntimeError("SAFETY_ROUTER_RUNTIME_INPUT_SCHEMA_INVALID")
    return result


def business_rule_decision(runtime: dict[str, Any]) -> dict[str, Any]:
    text = str(runtime["reviewText"])
    existing = set(runtime["matchedRiskSignals"])
    matched: set[str] = set()
    existing_mapping = {
        "paid_review": "paid_review",
        "rating_manipulation": "rating_manipulation",
        "review_suppression": "review_suppression",
        "fake_review": "fake_review",
        "safety_or_fraud_risk": "fraud",
    }
    for source, target in existing_mapping.items():
        if source in existing:
            matched.add(target)
    for risk, patterns in BUSINESS_RISK_PATTERNS.items():
        if any(re.search(pattern, text, re.I) for pattern in patterns):
            matched.add(risk)
    after_sales_signal = "after_sales_risk" in existing or bool(AFTER_SALES_PATTERN.search(text))
    if after_sales_signal and COMPLEXITY_PATTERN.search(text):
        matched.add("complex_after_sales")
    abstention_signal = bool(ABSTENTION_PATTERN.search(text))
    return {
        "matchedBusinessRisks": sorted(matched),
        "businessHighRiskTriggered": bool(matched),
        "abstentionSignal": abstention_signal,
        "safetyGateTriggered": bool(runtime["safetyGateTriggered"]),
    }


def safety_decision(probabilities: list[float]) -> dict[str, Any]:
    if len(probabilities) != len(SAFETY_CATEGORIES):
        raise RuntimeError("DUOGUARD_CATEGORY_COUNT_MISMATCH")
    score = max(probabilities)
    categories = [name for name, probability in zip(SAFETY_CATEGORIES, probabilities) if probability > UNSAFE_THRESHOLD]
    return {
        "unsafe": score > UNSAFE_THRESHOLD,
        "riskCategories": categories,
        "score": round(float(score), 6),
        "model": MODEL_ID,
    }


def route_decision(safety: dict[str, Any], business: dict[str, Any]) -> dict[str, Any]:
    safety_only_reasons: list[str] = []
    if safety["unsafe"]:
        safety_only_reasons.append("SAFETY_MODEL_UNSAFE")
    safety_only_route = LONG_ANALYSIS_CHAIN if safety_only_reasons else FAST_SHORT_CHAIN
    combined_reasons = list(safety_only_reasons)
    if business["abstentionSignal"]:
        combined_reasons.append("RUNTIME_ABSTENTION_SIGNAL")
    if business["safetyGateTriggered"]:
        combined_reasons.append("EXISTING_SAFETY_GATE")
    if business["businessHighRiskTriggered"]:
        combined_reasons.append("BUSINESS_HIGH_RISK_RULE")
    combined_route = LONG_ANALYSIS_CHAIN if combined_reasons else FAST_SHORT_CHAIN
    return {
        "safetyModelOnlyRoute": safety_only_route,
        "safetyModelOnlyReasons": safety_only_reasons,
        "combinedRoute": combined_route,
        "combinedReasons": combined_reasons,
    }


def load_model(model_dir: Path, device: str) -> tuple[Any, Any, dict[str, Any]]:
    required = ("config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json")
    if any(not (model_dir / name).is_file() for name in required):
        raise RuntimeError("DUOGUARD_LOCAL_FILES_INCOMPLETE")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("DUOGUARD_CUDA_UNAVAILABLE")
    if device == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    target = torch.device(device)
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    tokenizer.pad_token = tokenizer.eos_token
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_dir),
        local_files_only=True,
        dtype=dtype,
    ).to(target).eval()
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    metadata = {
        "parameterCount": parameter_count,
        "device": device,
        "dtype": str(dtype).replace("torch.", ""),
    }
    return tokenizer, model, metadata


def infer_one(tokenizer: Any, model: Any, text: str, device: str) -> tuple[dict[str, Any], float]:
    encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=MAX_LENGTH).to(device)
    started = time.perf_counter_ns()
    with torch.inference_mode():
        logits = model(**encoded).logits
        probabilities = torch.sigmoid(logits)[0].float().cpu().tolist()
    if device == "cuda":
        torch.cuda.synchronize()
    latency_ms = (time.perf_counter_ns() - started) / 1_000_000
    return safety_decision(probabilities), latency_ms


def evaluation_row(case: dict[str, Any], rule_row: dict[str, Any], route: str) -> dict[str, Any]:
    derived = binary.derive_binary_target(case)
    prediction = binary.LONG_REQUIRED if route == LONG_ANALYSIS_CHAIN else binary.FAST_ELIGIBLE
    false_fast = derived["target"] == binary.LONG_REQUIRED and prediction == binary.FAST_ELIGIBLE
    return {
        "caseId": str(case["caseId"]),
        "binaryTarget": derived["target"],
        "finalPrediction": prediction,
        "falseFast": false_fast,
        "highRiskFalseFast": false_fast and derived["goldSeverity"] in {"high", "critical"},
        "materialSafetyFalseFast": false_fast and bool(rule_row["materialSafetyError"]),
        "evaluationTarget": binary.evaluation_target(case),
        "boundaryType": case.get("boundaryType"),
    }


def route_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = setfit.setfit_metrics(rows)
    metrics["longAnalysisRate"] = baseline.safe_ratio(metrics["predictionDistribution"][binary.LONG_REQUIRED], metrics["caseCount"])
    return metrics


def metric_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "longRecall": metrics["longRequiredRecall"],
        "fastCoverage": metrics["fastCoverage"],
        "fastPrecision": metrics["fastPrecision"],
        "falseFast": metrics["falseFastCount"],
        "highRiskFalseFast": metrics["highRiskFalseFastCount"],
        "safetyFalseFast": metrics["materialSafetyFalseFastCount"],
        "falseEscalationRate": metrics["falseEscalationRate"],
        "longAnalysisRate": metrics["longAnalysisRate"],
    }


def existing_baselines() -> dict[str, Any]:
    previous = json.loads((binary.DEFAULT_OUTPUT_DIR / "rule_vs_binary_bge_v1.json").read_text(encoding="utf-8"))
    rule_validation = previous["ruleBinaryBaseline"]["validation"]
    rule_boundary = previous["ruleBinaryBaseline"]["boundary"]
    setfit_validation = json.loads((setfit.DEFAULT_OUTPUT_DIR / "setfit_binary_validation_metrics_v1.json").read_text(encoding="utf-8"))
    setfit_boundary = json.loads((setfit.DEFAULT_OUTPUT_DIR / "setfit_binary_boundary_metrics_v1.json").read_text(encoding="utf-8"))
    rule_validation["longAnalysisRate"] = 1 - rule_validation["fastCoverage"]
    rule_boundary["longAnalysisRate"] = 1 - rule_boundary["fastCoverage"]
    setfit_validation["longAnalysisRate"] = 1 - setfit_validation["fastCoverage"]
    setfit_boundary["longAnalysisRate"] = 1 - setfit_boundary["fastCoverage"]
    return {
        "currentRuleRouter": {"validation": metric_summary(rule_validation), "boundary": metric_summary(rule_boundary)},
        "setfitBinaryRouter": {"validation": metric_summary(setfit_validation), "boundary": metric_summary(setfit_boundary)},
    }


def candidate_gate(validation: dict[str, Any], boundary: dict[str, Any]) -> tuple[str, str]:
    safety_failed = any(
        metrics["highRiskFalseFastCount"] > 0 or metrics["materialSafetyFalseFastCount"] > 0
        for metrics in (validation, boundary)
    )
    if safety_failed:
        return "FAIL_SAFETY", "SAFETY_GUARD_INSUFFICIENT_FOR_BUSINESS_RISK_ROUTING"
    if validation["fastCoverage"] < 0.10:
        return "FAIL_COVERAGE", "SAFETY_GUARD_ROUTER_OVER_CONSERVATIVE"
    if validation["longRequiredRecall"] >= 0.95 and validation["fastCoverage"] >= 0.20:
        return "PASS", "SAFETY_GUARD_ROUTER_SHADOW_MODE"
    if validation["longRequiredRecall"] >= 0.90 and validation["fastCoverage"] >= 0.10:
        return "PASS_WITH_LIMITATIONS", "SAFETY_GUARD_ROUTER_SHADOW_MODE"
    return "FAIL_COVERAGE", "SAFETY_GUARD_ROUTER_QUALITY_INSUFFICIENT"


def percentile_metrics(values: list[float]) -> dict[str, float]:
    return {
        "p50Ms": baseline.percentile(values, 0.50),
        "p95Ms": baseline.percentile(values, 0.95),
        "p99Ms": baseline.percentile(values, 0.99),
    }


def build_report(manifest: dict[str, Any], comparison: dict[str, Any], gate: dict[str, Any]) -> str:
    combined = comparison["safetyModelPlusBusinessRules"]
    return "\n".join(
        [
            "# Safety Guard Router Report",
            "",
            "## Scope",
            "",
            "Step 21.3G evaluates one frozen open-source safety model, both alone and with an isolated business-rule layer. No training, Frozen benchmark, runtime Router change, Long Analysis, or external inference API call occurred.",
            "",
            "## Model",
            "",
            f"`{manifest['model']}` revision `{manifest['revision']}`, `{manifest['parameterCount']}` parameters, `{manifest['license']}`, `{manifest['device']}` `{manifest['dtype']}`.",
            f"Safety latency: `{json.dumps(manifest['latency']['safetyModel'], sort_keys=True)}`. End-to-end: `{json.dumps(manifest['latency']['endToEndRouter'], sort_keys=True)}`.",
            "",
            "## Results",
            "",
            f"Safety model only Validation: `{json.dumps(comparison['safetyModelOnly']['validation'], sort_keys=True)}`",
            f"Safety model plus business rules Validation: `{json.dumps(combined['validation'], sort_keys=True)}`",
            f"Safety model plus business rules Boundary: `{json.dumps(combined['boundary'], sort_keys=True)}`",
            f"Hard negative: `{json.dumps(combined['boundarySlices']['hardNegative'], sort_keys=True)}`",
            f"Abstention: `{json.dumps(combined['boundarySlices']['abstention'], sort_keys=True)}`",
            "",
            "## Gates",
            "",
            f"`STEP21_3G_GATE = {gate['step21_3gGate']}`",
            f"`SAFETY_GUARD_ROUTER_CANDIDATE_GATE = {gate['safetyGuardRouterCandidateGate']}`",
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
            "LANGFUSE_ENABLED": "false",
        }
    )
    protected = [baseline.DEFAULT_CALIBRATION, baseline.DEFAULT_BOUNDARY, baseline.DEFAULT_FROZEN]
    before = {str(path): baseline.sha256_file(path) for path in protected}
    expected = {
        str(baseline.DEFAULT_CALIBRATION): baseline.CALIBRATION_SHA,
        str(baseline.DEFAULT_BOUNDARY): baseline.BOUNDARY_SHA,
        str(baseline.DEFAULT_FROZEN): baseline.FROZEN_GOLD_SHA,
    }
    if before != expected:
        raise RuntimeError("STEP213G_PROTECTED_DATASET_HASH_MISMATCH")

    fit_cases, validation_cases, boundary_cases, rule_by_id = binary.load_partitions()
    all_cases = fit_cases + validation_cases + boundary_cases
    tokenizer, model, model_metadata = load_model(args.model_dir, args.device)
    with torch.inference_mode():
        infer_one(tokenizer, model, str(all_cases[0]["textZh"]), args.device)

    safety_latencies: list[float] = []
    router_latencies: list[float] = []
    safety_predictions: list[dict[str, Any]] = []
    business_predictions: list[dict[str, Any]] = []
    evaluation: dict[str, dict[str, list[dict[str, Any]]]] = {
        "safetyModelOnly": {"FIT": [], "VALIDATION": [], "BOUNDARY_CHALLENGE": []},
        "combined": {"FIT": [], "VALIDATION": [], "BOUNDARY_CHALLENGE": []},
    }
    decision_by_id: dict[str, tuple[bool, str]] = {}
    for case in all_cases:
        total_started = time.perf_counter_ns()
        runtime = runtime_input(case, rule_by_id[case["caseId"]])
        safety, model_latency = infer_one(tokenizer, model, runtime["reviewText"], args.device)
        business = business_rule_decision(runtime)
        routes = route_decision(safety, business)
        router_latency = (time.perf_counter_ns() - total_started) / 1_000_000
        safety_latencies.append(model_latency)
        router_latencies.append(router_latency)
        safety_predictions.append(
            {
                "caseId": str(case["caseId"]),
                "datasetPartition": str(case["_partition"]),
                "safetyDecision": safety,
                "latencyMs": round(model_latency, 6),
            }
        )
        business_predictions.append(
            {
                "caseId": str(case["caseId"]),
                "datasetPartition": str(case["_partition"]),
                "runtimeInputHash": stable_hash(runtime),
                "businessDecision": business,
                **routes,
            }
        )
        partition = str(case["_partition"])
        evaluation["safetyModelOnly"][partition].append(evaluation_row(case, rule_by_id[case["caseId"]], routes["safetyModelOnlyRoute"]))
        evaluation["combined"][partition].append(evaluation_row(case, rule_by_id[case["caseId"]], routes["combinedRoute"]))
        decision_by_id[str(case["caseId"])] = (bool(safety["unsafe"]), str(routes["combinedRoute"]))

    stability_cases = all_cases[:20]
    stable = 0
    for case in stability_cases:
        runtime = runtime_input(case, rule_by_id[case["caseId"]])
        safety, _ = infer_one(tokenizer, model, runtime["reviewText"], args.device)
        route = route_decision(safety, business_rule_decision(runtime))["combinedRoute"]
        stable += (bool(safety["unsafe"]), str(route)) == decision_by_id[str(case["caseId"])]

    safety_validation = route_metrics(evaluation["safetyModelOnly"]["VALIDATION"])
    safety_boundary = route_metrics(evaluation["safetyModelOnly"]["BOUNDARY_CHALLENGE"])
    combined_validation = route_metrics(evaluation["combined"]["VALIDATION"])
    combined_boundary = route_metrics(evaluation["combined"]["BOUNDARY_CHALLENGE"])
    combined_fit = route_metrics(evaluation["combined"]["FIT"])
    by_boundary_type = {
        kind: route_metrics([row for row in evaluation["combined"]["BOUNDARY_CHALLENGE"] if str(row["boundaryType"]) == kind])
        for kind in sorted({str(row["boundaryType"]) for row in evaluation["combined"]["BOUNDARY_CHALLENGE"]})
    }
    hard_negative = by_boundary_type["hard_negative"]
    abstention = combined_boundary["abstentionLongCapture"]

    allocated = round(torch.cuda.max_memory_allocated() / 1048576, 2) if args.device == "cuda" else 0.0
    reserved = round(torch.cuda.max_memory_reserved() / 1048576, 2) if args.device == "cuda" else 0.0
    latency = {
        "mode": "warm-single-request-batch-size-1",
        "caseCount": len(all_cases),
        "safetyModel": percentile_metrics(safety_latencies),
        "endToEndRouter": percentile_metrics(router_latencies),
    }
    manifest = {
        "schemaVersion": "safety-model-manifest-v1",
        "model": MODEL_ID,
        "revision": MODEL_REVISION,
        "license": MODEL_LICENSE,
        "parameterCount": model_metadata["parameterCount"],
        "device": model_metadata["device"],
        "dtype": model_metadata["dtype"],
        "modelPathIdentity": "<repo-external>/models/DuoGuard-0.5B",
        "modelWeightsSha": baseline.sha256_file(args.model_dir / "model.safetensors"),
        "tokenizer": TOKENIZER_ID,
        "tokenizerRevision": TOKENIZER_REVISION,
        "unsafeThreshold": UNSAFE_THRESHOLD,
        "categoryCount": len(SAFETY_CATEGORIES),
        "categories": list(SAFETY_CATEGORIES),
        "modelParametersModified": False,
        "trainingExecuted": False,
        "externalInferenceApiCallCount": 0,
        "latency": latency,
        "gpuMemory": {"peakAllocatedMiB": allocated, "peakReservedMiB": reserved},
    }
    policy = {
        "schemaVersion": "safety-router-policy-v1",
        "policyVersion": "step21.3g-safety-guard-assisted-v1",
        "longRequiredWhenAny": [
            "safetyDecision.unsafe == true",
            "businessDecision.businessHighRiskTriggered == true",
            "businessDecision.abstentionSignal == true",
            "businessDecision.safetyGateTriggered == true",
        ],
        "otherwise": FAST_SHORT_CHAIN,
        "safetyOutputMappedToBusinessRiskRegistry": False,
        "runtimeInputFields": list(RUNTIME_INPUT_FIELDS),
        "prohibitedRuntimeFields": sorted(PROHIBITED_RUNTIME_FIELDS),
        "businessRiskRules": sorted([*BUSINESS_RISK_PATTERNS, "complex_after_sales"]),
        "businessRuleUsesSafetyModelOutput": False,
        "frozenGoldUsed": False,
    }
    comparison = {
        "schemaVersion": "router-comparison-safety-guard-v1",
        "binaryTargetUnchanged": True,
        "sameValidationCases": True,
        "sameBoundaryCases": True,
        **existing_baselines(),
        "safetyModelOnly": {
            "validation": metric_summary(safety_validation),
            "boundary": metric_summary(safety_boundary),
        },
        "safetyModelPlusBusinessRules": {
            "fit": metric_summary(combined_fit),
            "validation": metric_summary(combined_validation),
            "boundary": metric_summary(combined_boundary),
            "boundarySlices": {
                kind: metric_summary(metrics) for kind, metrics in by_boundary_type.items()
            }
            | {
                "hardNegative": {
                    "caseCount": hard_negative["caseCount"],
                    "fastCoverage": hard_negative["fastCoverage"],
                    "falseEscalationCount": hard_negative["falseEscalationCount"],
                    "falseEscalationRate": hard_negative["falseEscalationRate"],
                },
                "abstention": abstention,
            },
        },
        "stability": {
            "caseCount": len(stability_cases),
            "consistentCount": stable,
            "decisionConsistency": baseline.safe_ratio(stable, len(stability_cases)),
        },
    }

    candidate, recommendation = candidate_gate(combined_validation, combined_boundary)
    after = {str(path): baseline.sha256_file(path) for path in protected}
    if before != after:
        raise RuntimeError("STEP213G_PROTECTED_DATASET_CHANGED")
    gate = {
        "safetyModelAvailabilityGate": "PASS",
        "safetyModelRuntimeGate": "PASS",
        "businessRuleGate": "PASS",
        "safetyRoutingGate": "PASS" if candidate in {"PASS", "PASS_WITH_LIMITATIONS"} else candidate,
        "boundaryGate": "PASS" if combined_boundary["highRiskFalseFastCount"] == 0 and combined_boundary["materialSafetyFalseFastCount"] == 0 else "FAIL_SAFETY",
        "latencyGate": "PASS" if latency["endToEndRouter"]["p95Ms"] <= 200 else "PASS_WITH_LIMITATIONS",
        "modelTrainingGate": "PASS",
        "datasetReadOnlyGate": "PASS",
        "runtimeInputIsolationGate": "PASS",
        "step21_3gGate": "PASS",
        "safetyGuardRouterCandidateGate": candidate,
        "nextRecommendation": recommendation,
        "frozenBenchmarkExecuted": False,
        "longAnalysisExecuted": False,
        "runtimeRouterModified": False,
        "modelParametersModified": False,
        "externalApiCallCount": 0,
        "calibrationSha": after[str(baseline.DEFAULT_CALIBRATION)],
        "boundarySha": after[str(baseline.DEFAULT_BOUNDARY)],
        "frozenGoldSha": after[str(baseline.DEFAULT_FROZEN)],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_json(args.output_dir / "safety_model_manifest_v1.json", manifest)
    baseline.write_jsonl(args.output_dir / "safety_model_predictions_v1.jsonl", safety_predictions)
    baseline.write_jsonl(args.output_dir / "business_rule_predictions_v1.jsonl", business_predictions)
    baseline.write_json(args.output_dir / "safety_router_policy_v1.json", policy)
    baseline.write_json(args.output_dir / "router_comparison_safety_guard_v1.json", comparison)
    baseline.write_json(args.output_dir / "step213g_gate_v1.json", gate)
    args.report.write_text(build_report(manifest, comparison, gate), encoding="utf-8", newline="\n")
    return {"manifest": manifest, "comparison": comparison, "gate": gate}


def main() -> int:
    result = run(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
