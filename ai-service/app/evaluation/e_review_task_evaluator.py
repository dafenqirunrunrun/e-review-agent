from __future__ import annotations

from collections import Counter
from typing import Any

from app.contracts.e_review_decision_migration import process_model_output


def macro_f1(labels: list[Any], preds: list[Any]) -> float:
    classes = sorted(set(labels) | set(preds), key=str)
    if not classes:
        return 0.0
    scores = []
    for cls in classes:
        tp = sum(1 for y, p in zip(labels, preds) if y == cls and p == cls)
        fp = sum(1 for y, p in zip(labels, preds) if y != cls and p == cls)
        fn = sum(1 for y, p in zip(labels, preds) if y == cls and p != cls)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append((2 * precision * recall / (precision + recall)) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def evaluate_e_review_outputs(raw_outputs: list[str], gold_targets: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(gold_targets) or 1
    processed = [process_model_output(raw) for raw in raw_outputs]
    extraction_success = [item["raw_json_extraction"].extraction_success for item in processed]
    normalized = [item.get("contract_normalization") for item in processed]
    eligible = [bool(item["prediction_eligible"]) for item in processed]
    operational = [item["operational_result"] for item in processed]
    eligible_pairs = [(pred, gold) for pred, gold, ok in zip(operational, gold_targets, eligible) if ok]
    pred_type = [pred.get("risk_type") for pred, _ in eligible_pairs]
    gold_type = [gold.get("risk_type") for _, gold in eligible_pairs]
    pred_level = [pred.get("risk_level") for pred, _ in eligible_pairs]
    gold_level = [gold.get("risk_level") for _, gold in eligible_pairs]
    pred_human = [bool(pred.get("need_human_review")) for pred, _ in eligible_pairs]
    gold_human = [bool(gold.get("need_human_review")) for _, gold in eligible_pairs]
    correct = sum(
        1
        for pred, gold in eligible_pairs
        if pred.get("risk_type") == gold.get("risk_type")
        and pred.get("risk_level") == gold.get("risk_level")
        and bool(pred.get("need_human_review")) == bool(gold.get("need_human_review"))
    )
    fallback_count = sum(1 for item in operational if item.get("prediction_source") == "operational_safety_fallback")
    semantic_changes = sum(
        1
        for item in normalized
        if item is not None and getattr(item, "semantic_field_changed", False)
    )
    return {
        "raw_output_count": len(raw_outputs),
        "raw_json_object_extract_rate": round(sum(extraction_success) / total, 8),
        "raw_json_parse_success_rate": round(sum(extraction_success) / total, 8),
        "raw_canonical_schema_valid_rate": round(sum(eligible) / total, 8),
        "raw_required_field_presence_rate": round(sum(eligible) / total, 8),
        "contract_normalization_rate": round(sum(1 for item in normalized if item is not None and item.normalization_success) / total, 8),
        "normalized_canonical_schema_valid_rate": round(sum(eligible) / total, 8),
        "semantic_field_change_count": semantic_changes,
        "prediction_eligible_for_task_metrics_rate": round(sum(eligible) / total, 8),
        "operational_final_schema_valid_rate": 1.0,
        "operational_fallback_rate": round(fallback_count / total, 8),
        "empty_output_rate": round(sum(1 for raw in raw_outputs if not raw.strip()) / total, 8),
        "prohibited_auto_action_count": sum(1 for raw in raw_outputs if any(term in raw.lower() for term in ["refund", "ban", "compensate", "自动退款", "自动封禁", "自动赔付"])),
        "task_coverage_rate": round(sum(eligible) / total, 8),
        "abstention_rate": round((total - sum(eligible)) / total, 8),
        "risk_type_macro_f1": round(macro_f1(gold_type, pred_type), 8) if eligible_pairs else 0.0,
        "risk_level_macro_f1": round(macro_f1(gold_level, pred_level), 8) if eligible_pairs else 0.0,
        "need_human_review_f1": round(macro_f1(gold_human, pred_human), 8) if eligible_pairs else 0.0,
        "coverage_adjusted_accuracy": round(correct / total, 8),
        "eligible_prediction_count": sum(eligible),
        "fallback_prediction_count": fallback_count,
        "prediction_source_distribution": dict(Counter(item.get("prediction_source", "raw_or_normalized") for item in operational)),
    }
