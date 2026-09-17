import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.metrics.human_review import compute_human_review_route_metrics, route_metric_input_from_labels
from app.rag_v2.corpus_loader import load_jsonl


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "multimodal" / "eval" / "route_calibration_results.json"
REPORT = ROOT / "docs" / "119_v161_multimodal_route_calibration_report.md"


def safe_load(path: Path):
    return load_jsonl(path) if path.exists() else []


def metric_definitions():
    return {
        "human_review_accuracy": "(TP + TN) / all",
        "human_review_precision": "TP / (TP + FP)",
        "human_review_recall": "TP / (TP + FN)",
        "human_review_f1": "2PR / (P + R)",
        "high_risk_review_recall": "high risk samples routed to human / all high risk samples",
        "review_trigger_rate": "samples routed to human / all samples",
        "unsafe_auto_pass_rate": "samples that should be human-reviewed but auto-passed / all samples that should be human-reviewed",
    }


def _table_from_dict(values: dict) -> str:
    lines = []
    for key, value in values.items():
        if isinstance(value, float):
            lines.append(f"| {key} | {value:.4f} |")
        else:
            lines.append(f"| {key} | {value} |")
    return "\n".join(lines)


def report_text(result):
    metrics = "\n".join(f"| {key} | {value} |" for key, value in result["metric_definitions"].items())
    reasons = "\n".join(f"- {item}" for item in result["blocking_reasons"])
    synthetic_metrics = result.get("synthetic_label_policy_sanity_check")
    synthetic_table = _table_from_dict(synthetic_metrics) if synthetic_metrics else "| status | not_available |"
    return f"""# v1.6.1 Multimodal Human Review Route Calibration Report

## Conclusion

`{result['marker']}`

Real-world route calibration is blocked because the allowed calibration inputs are not ready. External test sets must not be used for threshold calibration, prompt selection, or fusion-weight tuning.

The synthetic validation result below is only a label-policy sanity check for the metric implementation and safety routing rules. It is not a model prediction result, not a real-world calibration result, and must not trigger a PASS marker.

## Metric Definitions

| Metric | Definition |
| --- | --- |
{metrics}

## Synthetic Label-Policy Sanity Check

This check uses `risk_type` and `risk_level` labels from synthetic validation data to verify that metric calculation and route rules are executable. It is not evidence of real-world generalization.

| metric | value |
| --- | --- |
{synthetic_table}

## Blocking Reasons

{reasons}

## Safety Constraints

1. Route to human review when `visual_tool_failed` is true.
2. Prefer human review when `text_image_consistency=conflicting`.
3. Target `high_risk_review_recall >= 0.95`.
4. Target `unsafe_auto_pass_rate <= 0.05`.
5. Do not use real external test sets for threshold tuning.
"""


def main() -> int:
    synthetic_validation = [
        row
        for row in safe_load(ROOT / "data/rag/comments/review_samples_1200.jsonl")
        if row.get("split") == "validation"
    ]
    real_dev = safe_load(ROOT / "data/real_world/processed/real_reviews_dev_400.jsonl")
    multimodal_validation = safe_load(ROOT / "data/real_world/multimodal_manifest/real_multimodal_validation.jsonl")
    synthetic_metrics = None
    if synthetic_validation:
        synthetic_metrics = compute_human_review_route_metrics(
            route_metric_input_from_labels(row) for row in synthetic_validation
        )

    blocking = []
    if not synthetic_validation:
        blocking.append("synthetic validation data is missing")
    if len(real_dev) < 400:
        blocking.append(f"real_world dev requires at least 400 text samples; current={len(real_dev)}")
    if len(multimodal_validation) < 40:
        blocking.append(
            f"multimodal validation requires at least 40 image-text samples; current={len(multimodal_validation)}"
        )

    result = {
        "marker": "REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_BLOCKED"
        if blocking
        else "REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_READY",
        "metric_definitions": metric_definitions(),
        "synthetic_label_policy_sanity_check": synthetic_metrics,
        "calibration_status": "synthetic_only_not_real_calibration" if synthetic_metrics else "not_available",
        "blocking_reasons": blocking,
        "counts": {
            "synthetic_validation": len(synthetic_validation),
            "real_dev": len(real_dev),
            "multimodal_validation": len(multimodal_validation),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    print(result["marker"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
