from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RootCause:
    code: str
    confidence: float
    supporting_metrics: dict[str, Any]
    contradicting_evidence: list[str]
    recommended_intervention: str
    single_major_factor_change: str


def determine_no_go_root_causes(report: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = report.get("validation_metrics", {})
    base = metrics.get("base", {})
    adapter = metrics.get("adapter", {})
    distribution = report.get("class_distribution_analysis", {})
    template = report.get("target_template_analysis", {})
    diversity = report.get("scenario_diversity_analysis", {})
    token = report.get("token_objective_analysis", {})
    curve = report.get("training_curve_analysis", {})
    causes: list[RootCause] = []

    if base.get("raw_canonical_schema_valid_rate", 0) >= 0.8:
        causes.append(
            RootCause(
                "ROOT_CAUSE_BASE_ALREADY_STRONG_ON_SCHEMA",
                0.72,
                {"base_raw_schema": base.get("raw_canonical_schema_valid_rate"), "adapter_raw_schema": adapter.get("raw_canonical_schema_valid_rate")},
                [],
                "Use validation-only diagnosis to target task semantics rather than schema format.",
                "data_distribution",
            )
        )
    if adapter.get("coverage_adjusted_accuracy", 0) <= base.get("coverage_adjusted_accuracy", 0) + 0.02 and adapter.get("task_coverage_rate", 0) <= base.get("task_coverage_rate", 0):
        causes.append(
            RootCause(
                "ROOT_CAUSE_ADAPTER_NO_TASK_GAIN",
                0.9,
                {
                    "base_coverage_adjusted_accuracy": base.get("coverage_adjusted_accuracy"),
                    "adapter_coverage_adjusted_accuracy": adapter.get("coverage_adjusted_accuracy"),
                    "base_task_coverage": base.get("task_coverage_rate"),
                    "adapter_task_coverage": adapter.get("task_coverage_rate"),
                },
                [],
                "Prioritize new scenario-balanced synthetic data before any hyperparameter change.",
                "synthetic_v23_data",
            )
        )
    if distribution.get("adapter_classification") in {"PARTIAL_COLLAPSE", "CLASS_BIAS"}:
        causes.append(
            RootCause(
                "ROOT_CAUSE_CLASS_PREDICTION_BIAS",
                0.78,
                {"adapter_dominant_class_rate": distribution.get("adapter_dominant_class_rate"), "adapter_js_divergence": distribution.get("adapter_js_divergence")},
                [],
                "Add balanced boundary pairs and class-contrast examples in v2.3.",
                "synthetic_v23_data",
            )
        )
    if template.get("template_signal") == "TARGET_TEMPLATE_OVERFIT_RISK":
        causes.append(
            RootCause(
                "ROOT_CAUSE_TARGET_TEMPLATE_OVERFIT",
                0.74,
                {
                    "normalized_target_duplicate_rate": template.get("normalized_target_duplicate_rate"),
                    "route_reason_top1_share": template.get("route_reason_top1_share"),
                },
                [],
                "Increase target wording diversity while preserving canonical labels.",
                "target_diversity",
            )
        )
    if diversity.get("scenario_diversity_status") == "SCENARIO_DIVERSITY_WEAK":
        causes.append(
            RootCause(
                "ROOT_CAUSE_SYNTHETIC_SCENARIO_HOMOGENEITY",
                0.8,
                {"scenario_family_count": diversity.get("scenario_family_count"), "boundary_sample_count": diversity.get("boundary_sample_count")},
                [],
                "Generate v2.3 with explicit boundary and contrast quotas.",
                "synthetic_v23_data",
            )
        )
    if token.get("status") == "SFT_TOKEN_OBJECTIVE_ALIGNMENT_WEAK":
        causes.append(
            RootCause(
                "ROOT_CAUSE_SEMANTIC_LABEL_TOKEN_UNDERWEIGHT",
                0.62,
                {"semantic_label_token_ratio": token.get("semantic_label_token_ratio")},
                ["Token ratio alone is medium evidence and cannot be the only root cause."],
                "Keep schema fixed but rebalance examples so semantic labels are less template-correlated.",
                "synthetic_v23_data",
            )
        )
    if curve.get("loss_improved_task_not_improved"):
        causes.append(
            RootCause(
                "ROOT_CAUSE_FORMAT_LEARNING_WITHOUT_TASK_GAIN",
                0.76,
                {"train_loss_reduction_relative": curve.get("relative_train_loss_reduction"), "final_validation_loss": curve.get("final_validation_loss")},
                [],
                "Do not add epochs first; test data-first v2.3 Experiment A.",
                "synthetic_v23_data",
            )
        )
    if not causes:
        causes.append(
            RootCause(
                "ROOT_CAUSE_UNRESOLVED",
                0.4,
                {},
                ["Available validation-only metrics did not isolate a deterministic root cause."],
                "Collect richer validation predictions before changing training.",
                "analysis_only",
            )
        )
    return [cause.__dict__ for cause in causes]
