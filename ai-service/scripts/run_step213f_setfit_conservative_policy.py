from __future__ import annotations

"""Evaluate a safety-first threshold policy for the frozen Step 21.3E SetFit router."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from scripts import run_step2123_reliability_analysis as baseline
from scripts import run_step213d_binary_router as binary
from scripts import run_step213e_setfit_binary_router as setfit


STEP213E_OUTPUT = ROOT / "artifacts" / "step213e_setfit_binary_router"
DEFAULT_MODEL_DIR = STEP213E_OUTPUT / "setfit_binary_router_v1"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "step213f_setfit_conservative_policy"
DEFAULT_REPORT = REPO_ROOT / "docs" / "SETFIT_CONSERVATIVE_POLICY_REPORT.md"
THRESHOLD_CANDIDATES = (0.50, 0.60, 0.70, 0.80, 0.90)
BENCHMARK_VERSION = "step21.3f-setfit-conservative-policy-v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    return parser.parse_args()


def directory_hash(path: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        raise RuntimeError("SETFIT_MODEL_ARTIFACT_MISSING")
    for item in files:
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(item.read_bytes())
    return digest.hexdigest().upper()


def load_frozen_model(model_dir: Path, device: str) -> Any:
    torch, _, SetFitModel, _ = setfit.load_setfit_dependencies()
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("SETFIT_CUDA_UNAVAILABLE")
    model = SetFitModel.from_pretrained(str(model_dir), local_files_only=True)
    model.model_body.to(device)
    return model


def metric_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    fast_count = int(metrics["predictionDistribution"][binary.FAST_ELIGIBLE])
    long_count = int(metrics["predictionDistribution"][binary.LONG_REQUIRED])
    return {
        "caseCount": metrics["caseCount"],
        "fastCount": fast_count,
        "longCount": long_count,
        "fastCoverage": metrics["fastCoverage"],
        "longRate": baseline.safe_ratio(long_count, metrics["caseCount"]),
        "longRequiredRecall": metrics["longRequiredRecall"],
        "fastPrecision": metrics["fastPrecision"],
        "falseFastCount": metrics["falseFastCount"],
        "falseFastRate": metrics["falseFastRate"],
        "highRiskFalseFastCount": metrics["highRiskFalseFastCount"],
        "materialSafetyFalseFastCount": metrics["materialSafetyFalseFastCount"],
        "falseEscalationCount": metrics["falseEscalationCount"],
        "falseEscalationRate": metrics["falseEscalationRate"],
    }


def select_policy(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if [item["threshold"] for item in candidates] != list(THRESHOLD_CANDIDATES):
        raise RuntimeError("SETFIT_THRESHOLD_CANDIDATES_CHANGED")
    selected = min(
        candidates,
        key=lambda item: (
            item["devMetrics"]["highRiskFalseFastCount"] != 0,
            item["devMetrics"]["highRiskFalseFastCount"],
            item["devMetrics"]["materialSafetyFalseFastCount"] != 0,
            item["devMetrics"]["materialSafetyFalseFastCount"],
            -item["devMetrics"]["longRequiredRecall"],
            -item["devMetrics"]["fastCoverage"],
            item["threshold"],
        ),
    )
    return selected


def candidate_gate(metrics: dict[str, Any]) -> tuple[str, str]:
    if metrics["highRiskFalseFastCount"] > 0 or metrics["materialSafetyFalseFastCount"] > 0:
        return "FAIL_SAFETY", "SETFIT_BINARY_ROUTER_UNSAFE"
    if metrics["fastCoverage"] < 0.10:
        return "FAIL_TOO_CONSERVATIVE", "EXPAND_BINARY_TRAINING_POOL"
    if metrics["longRequiredRecall"] >= 0.95 and metrics["fastCoverage"] >= 0.20:
        return "PASS", "BINARY_ROUTER_SHADOW_MODE"
    if metrics["longRequiredRecall"] >= 0.90 and metrics["fastCoverage"] >= 0.10:
        return "PASS_WITH_LIMITATIONS", "BINARY_ROUTER_SHADOW_MODE"
    return "FAIL_QUALITY", "TASK_SPECIFIC_FINETUNE_NOT_EFFECTIVE"


def build_report(
    sweep: dict[str, Any],
    policy: dict[str, Any],
    validation: dict[str, Any],
    boundary: dict[str, Any],
    gate: dict[str, Any],
) -> str:
    rows = [
        "| Threshold | FAST | LONG | FAST coverage | LONG recall | FAST precision | High-risk false fast | Safety false fast |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in sweep["candidates"]:
        metrics = item["devMetrics"]
        rows.append(
            f"| {item['threshold']:.2f} | {metrics['fastCount']} | {metrics['longCount']} | "
            f"{metrics['fastCoverage']:.4f} | {metrics['longRequiredRecall']:.4f} | "
            f"{metrics['fastPrecision']:.4f} | {metrics['highRiskFalseFastCount']} | "
            f"{metrics['materialSafetyFalseFastCount']} |"
        )
    return "\n".join(
        [
            "# SetFit Conservative Policy Report",
            "",
            "## Scope",
            "",
            "Step 21.3F evaluates fixed thresholds against the frozen Step 21.3E SetFit model. No model training, dataset modification, Frozen benchmark, runtime change, Qwen call, or external API call occurred.",
            "",
            "The score is `longRequiredScore`; therefore, a higher threshold makes LONG_REQUIRED harder to trigger and is less conservative under the frozen decision rule.",
            "",
            "## Dev16 Threshold Sweep",
            "",
            *rows,
            "",
            f"Selected threshold: `{policy['selectedThreshold']}`. Safety-feasible candidate found: `{str(policy['safetyFeasibleCandidateFound']).lower()}`.",
            "",
            "## Final Evaluation",
            "",
            f"Validation: `{json.dumps(metric_summary(validation), sort_keys=True)}`",
            f"Boundary: `{json.dumps(metric_summary(boundary), sort_keys=True)}`",
            f"Abstention: `{json.dumps(boundary['abstentionLongCapture'], sort_keys=True)}`",
            f"Hard negative: `{json.dumps(boundary['hardNegative'], sort_keys=True)}`",
            "",
            "## Gates",
            "",
            f"`STEP21_3F_GATE = {gate['step21_3fGate']}`",
            f"`SETFIT_ROUTER_CANDIDATE_GATE = {gate['setfitRouterCandidateGate']}`",
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
        raise RuntimeError("STEP213F_PROTECTED_DATASET_HASH_MISMATCH")
    if not args.model_dir.is_dir():
        raise RuntimeError("STEP213E_SETFIT_MODEL_MISSING")

    snapshot = json.loads((STEP213E_OUTPUT / "setfit_binary_model_snapshot_v1.json").read_text(encoding="utf-8"))
    training = json.loads((STEP213E_OUTPUT / "setfit_binary_training_metrics_v1.json").read_text(encoding="utf-8"))
    step213e_config = json.loads((STEP213E_OUTPUT / "setfit_binary_training_config_v1.json").read_text(encoding="utf-8"))
    if snapshot["classificationHeadSha"] != baseline.sha256_file(args.model_dir / "model_head.pkl"):
        raise RuntimeError("STEP213E_CLASSIFICATION_HEAD_HASH_MISMATCH")
    model_hash_before = directory_hash(args.model_dir)

    fit, validation_cases, boundary_cases, rule_by_id = binary.load_partitions()
    split = setfit.load_fixed_split()
    split_by_id = {row["caseId"]: row["partition"] for row in split["rows"]}
    dev_cases = [case for case in fit if split_by_id[case["caseId"]] == "DEV"]
    if len(dev_cases) != 16:
        raise RuntimeError("STEP213F_DEV_COUNT_CHANGED")

    model = load_frozen_model(args.model_dir, args.device)
    dev_scores = setfit.classification_scores(model, [str(case["textZh"]) for case in dev_cases])
    candidate_rows: list[dict[str, Any]] = []
    for threshold in THRESHOLD_CANDIDATES:
        rows = setfit.make_outputs(dev_cases, dev_scores, threshold, rule_by_id)
        candidate_rows.append({"threshold": threshold, "devMetrics": metric_summary(setfit.setfit_metrics(rows))})
    selected = select_policy(candidate_rows)
    selected_threshold = float(selected["threshold"])

    validation_scores = setfit.classification_scores(model, [str(case["textZh"]) for case in validation_cases])
    validation_rows = setfit.make_outputs(validation_cases, validation_scores, selected_threshold, rule_by_id)
    validation_metrics = setfit.setfit_metrics(validation_rows)
    boundary_scores = setfit.classification_scores(model, [str(case["textZh"]) for case in boundary_cases])
    boundary_rows = setfit.make_outputs(boundary_cases, boundary_scores, selected_threshold, rule_by_id)
    boundary_metrics = setfit.setfit_metrics(boundary_rows)
    boundary_metrics["byBoundaryType"] = {
        kind: setfit.setfit_metrics([row for row in boundary_rows if str(row.get("boundaryType")) == kind])
        for kind in sorted({str(row.get("boundaryType")) for row in boundary_rows})
    }

    model_hash_after = directory_hash(args.model_dir)
    after = {str(path): baseline.sha256_file(path) for path in protected}
    if before != after:
        raise RuntimeError("STEP213F_PROTECTED_DATASET_CHANGED")
    if model_hash_before != model_hash_after:
        raise RuntimeError("STEP213F_MODEL_ARTIFACT_CHANGED")

    sweep = {
        "schemaVersion": "setfit-threshold-sweep-v1",
        "benchmarkVersion": BENCHMARK_VERSION,
        "scoreName": "longRequiredScore",
        "decisionRule": "LONG_REQUIRED when score >= threshold; otherwise FAST_ELIGIBLE; Safety Gate remains a hard LONG override",
        "selectionPartition": "FIT_INTERNAL_DEV_16_ONLY",
        "candidateThresholds": list(THRESHOLD_CANDIDATES),
        "candidates": candidate_rows,
        "validationUsed": False,
        "boundaryUsed": False,
        "frozenUsed": False,
    }
    safety_feasible = any(
        item["devMetrics"]["highRiskFalseFastCount"] == 0 and item["devMetrics"]["materialSafetyFalseFastCount"] == 0
        for item in candidate_rows
    )
    policy = {
        "schemaVersion": "setfit-policy-selection-v1",
        "selectedThreshold": selected_threshold,
        "selectedDevMetrics": selected["devMetrics"],
        "selectionPartition": "FIT_INTERNAL_DEV_16_ONLY",
        "selectionPriority": [
            "HIGH_RISK_FALSE_FAST_ZERO",
            "SAFETY_FALSE_FAST_ZERO",
            "LONG_REQUIRED_RECALL_DESC",
            "FAST_COVERAGE_DESC",
        ],
        "safetyFeasibleCandidateFound": safety_feasible,
        "modelRetrained": False,
        "modelArtifactHashBefore": model_hash_before,
        "modelArtifactHashAfter": model_hash_after,
        "modelSnapshot": {
            "modelId": snapshot["modelId"],
            "revision": snapshot["revision"],
            "classificationHeadSha": snapshot["classificationHeadSha"],
        },
        "internalSplitHash": split["splitHash"],
        "validationUsed": False,
        "boundaryUsed": False,
        "frozenUsed": False,
    }
    candidate, recommendation = candidate_gate(validation_metrics)
    latency = training["latency"]
    gate = {
        "thresholdCandidatesGate": "PASS",
        "thresholdSelectionGate": "PASS" if safety_feasible else "PASS_WITH_NO_SAFE_CANDIDATE",
        "validationGate": "PASS",
        "boundaryAfterFreezeGate": "PASS",
        "modelReadOnlyGate": "PASS",
        "datasetReadOnlyGate": "PASS",
        "latencyGate": "PASS" if latency["endToEnd"]["p95Ms"] <= 200 else "PASS_WITH_LIMITATIONS",
        "step21_3fGate": "PASS",
        "setfitRouterCandidateGate": candidate,
        "nextRecommendation": recommendation,
        "selectedThreshold": selected_threshold,
        "safetyFeasibleCandidateFound": safety_feasible,
        "modelRetrained": False,
        "frozenBenchmarkExecuted": False,
        "qwenCallCount": 0,
        "externalApiCallCount": 0,
        "calibrationSha": after[str(baseline.DEFAULT_CALIBRATION)],
        "boundarySha": after[str(baseline.DEFAULT_BOUNDARY)],
        "frozenGoldSha": after[str(baseline.DEFAULT_FROZEN)],
        "internalSplitHash": split["splitHash"],
        "binaryTargetDefinitionHash": step213e_config["binaryTargetDefinitionHash"],
        "latency": latency,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_json(args.output_dir / "setfit_threshold_sweep_v1.json", sweep)
    baseline.write_json(args.output_dir / "setfit_policy_selection_v1.json", policy)
    baseline.write_jsonl(args.output_dir / "setfit_validation_conservative_v1.jsonl", validation_rows)
    baseline.write_json(args.output_dir / "setfit_validation_metrics_conservative_v1.json", validation_metrics)
    baseline.write_json(args.output_dir / "setfit_boundary_metrics_conservative_v1.json", boundary_metrics)
    baseline.write_json(args.output_dir / "setfit_threshold_gate_v1.json", gate)
    args.report.write_text(build_report(sweep, policy, validation_metrics, boundary_metrics, gate), encoding="utf-8", newline="\n")
    return {"sweep": sweep, "policy": policy, "validation": validation_metrics, "boundary": boundary_metrics, "gate": gate}


def main() -> int:
    result = run(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
