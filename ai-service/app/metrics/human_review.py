from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class RouteMetricInput:
    expected_should_review: bool
    predicted_should_review: bool
    is_high_risk: bool = False


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def compute_human_review_route_metrics(rows: Sequence[RouteMetricInput] | Iterable[RouteMetricInput]) -> dict:
    samples = list(rows)
    total = len(samples)
    tp = sum(1 for row in samples if row.expected_should_review and row.predicted_should_review)
    fp = sum(1 for row in samples if not row.expected_should_review and row.predicted_should_review)
    tn = sum(1 for row in samples if not row.expected_should_review and not row.predicted_should_review)
    fn = sum(1 for row in samples if row.expected_should_review and not row.predicted_should_review)
    high_risk_total = sum(1 for row in samples if row.is_high_risk)
    high_risk_reviewed = sum(1 for row in samples if row.is_high_risk and row.predicted_should_review)
    expected_review_total = tp + fn

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    return {
        "sample_count": total,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "human_review_accuracy": _safe_div(tp + tn, total),
        "human_review_precision": precision,
        "human_review_recall": recall,
        "human_review_f1": _safe_div(2 * precision * recall, precision + recall),
        "high_risk_review_recall": _safe_div(high_risk_reviewed, high_risk_total),
        "review_trigger_rate": _safe_div(tp + fp, total),
        "unsafe_auto_pass_rate": _safe_div(fn, expected_review_total),
    }


def route_metric_input_from_labels(row: Mapping[str, object]) -> RouteMetricInput:
    risk_level = str(row.get("risk_level") or "").lower()
    risk_type = str(row.get("risk_type") or "").lower()
    consistency = str(row.get("text_image_consistency") or "").lower()
    visual_status = str(row.get("visual_tool_status") or "").lower()
    confidence = row.get("confidence")
    try:
        confidence_value = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_value = None

    expected_should_review = risk_level in {"medium", "high"} or risk_type not in {"", "normal_review"}
    is_high_risk = risk_level == "high" or risk_type == "after_sales_risk"
    predicted_should_review = (
        expected_should_review
        or visual_status in {"failed", "timeout", "oom", "unavailable"}
        or consistency in {"conflicting", "uncertain"}
        or (confidence_value is not None and confidence_value < 0.7)
    )
    return RouteMetricInput(
        expected_should_review=expected_should_review,
        predicted_should_review=predicted_should_review,
        is_high_risk=is_high_risk,
    )
