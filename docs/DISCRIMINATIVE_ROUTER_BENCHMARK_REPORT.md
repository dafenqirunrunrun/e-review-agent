# Discriminative Router Benchmark Report

## Scope

Step 21.3A.2 evaluates a frozen local BGE-M3 encoder with ten independent one-vs-rest logistic heads. It is offline-only: runtime Router, Safety Gate, Workflow, datasets, and Frozen Gold are unchanged.

## Encoder And Training

- Encoder: `BAAI/bge-m3` / `project-existing-transformers-cls-l2`.
- Device / dtype / dimension: `cuda:0` / `float32` / `1024`.
- Frozen encoder trainable parameter tensors: `0`.
- Fit label support: normal_review=26, negative_review=18, after_sales_risk=13, fake_review=5, paid_review=8, rating_manipulation=7, review_suppression=6, safety_or_fraud_risk=8, harassment_or_abuse=3, privacy_risk=1.
- Global threshold selected on Fit-internal Dev only: `0.3`.
- Final logistic training time: `50.714 ms`; embedding extraction: `3750.693 ms`.

## Rule Vs BGE-M3 Logistic

| Metric | Rule | BGE-M3 + LR |
| --- | ---: | ---: |
| Validation Exact | 0.4500 | 0.0000 |
| Validation Micro F1 | 0.4421 | 0.3153 |
| Boundary Micro F1 | 0.2981 | 0.3664 |
| Multi-risk Micro F1 | 0.2923 | 0.5338 |
| Material Safety Errors | 50 | 2 |

## Abstention And Reliability

Abstention accuracy `0.0000`. Scores are ordinal classification signals, not calibrated probabilities. Diagnostic: `{"GE_0_6_LT_0_8": {"accuracy": 0.0, "count": 58, "coverage": 0.58, "materialSafetyErrorCount": 0}, "GE_0_8": {"accuracy": null, "count": 0, "coverage": 0.0, "materialSafetyErrorCount": 0}, "GE_THRESHOLD_LT_0_6": {"accuracy": 0.0, "count": 42, "coverage": 0.42, "materialSafetyErrorCount": 2}}`.

## Single Request Latency

Embedding P50/P95 `23.17325/27.6926 ms`; classifier `2.12405/2.784555 ms`; end-to-end `25.3554/29.96987 ms`.

## Integrity

Calibration SHA `DB3B4B9692EBB08B1A4A0CC45715084369AEE4BD571BCBAED6FDBF297F6A48A3`; Boundary SHA `5472C19987A23F57BF121321D47958C1D5ED0344615E12C9714CD26A4A021730`; Frozen SHA `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`. Frozen was not executed. External API calls: `0`.

## Gates

- `bgeM3AvailabilityGate` = `PASS`
- `labelSupportGate` = `PASS_WITH_LIMITATIONS`
- `embeddingGate` = `PASS`
- `logisticTrainGate` = `PASS`
- `thresholdSelectionGate` = `PASS`
- `validationGate` = `PASS`
- `boundaryGate` = `PASS`
- `safetyEvaluationGate` = `PASS`
- `step21_3a_2Gate` = `PASS`
- `discriminativeRouterCandidateGate` = `FAIL`

## Conclusion

`LINEAR_EMBEDDING_ROUTER_INSUFFICIENT`
