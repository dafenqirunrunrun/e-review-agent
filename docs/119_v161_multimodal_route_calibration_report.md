# v1.6.1 Multimodal Human Review Route Calibration Report

## Conclusion

`REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_BLOCKED`

Real-world route calibration is blocked because the allowed calibration inputs are not ready. External test sets must not be used for threshold calibration, prompt selection, or fusion-weight tuning.

The synthetic validation result below is only a label-policy sanity check for the metric implementation and safety routing rules. It is not a model prediction result, not a real-world calibration result, and must not trigger a PASS marker.

## Metric Definitions

| Metric | Definition |
| --- | --- |
| human_review_accuracy | (TP + TN) / all |
| human_review_precision | TP / (TP + FP) |
| human_review_recall | TP / (TP + FN) |
| human_review_f1 | 2PR / (P + R) |
| high_risk_review_recall | high risk samples routed to human / all high risk samples |
| review_trigger_rate | samples routed to human / all samples |
| unsafe_auto_pass_rate | samples that should be human-reviewed but auto-passed / all samples that should be human-reviewed |

## Synthetic Label-Policy Sanity Check

This check uses `risk_type` and `risk_level` labels from synthetic validation data to verify that metric calculation and route rules are executable. It is not evidence of real-world generalization.

| metric | value |
| --- | --- |
| sample_count | 180 |
| true_positive | 153 |
| false_positive | 0 |
| true_negative | 27 |
| false_negative | 0 |
| human_review_accuracy | 1.0000 |
| human_review_precision | 1.0000 |
| human_review_recall | 1.0000 |
| human_review_f1 | 1.0000 |
| high_risk_review_recall | 1.0000 |
| review_trigger_rate | 0.8500 |
| unsafe_auto_pass_rate | 0.0000 |

## Blocking Reasons

- real_world dev requires at least 400 text samples; current=0
- multimodal validation requires at least 40 image-text samples; current=0

## Safety Constraints

1. Route to human review when `visual_tool_failed` is true.
2. Prefer human review when `text_image_consistency=conflicting`.
3. Target `high_risk_review_recall >= 0.95`.
4. Target `unsafe_auto_pass_rate <= 0.05`.
5. Do not use real external test sets for threshold tuning.
