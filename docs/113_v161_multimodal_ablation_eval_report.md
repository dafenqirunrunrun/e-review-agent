# v1.6.1 Multimodal Ablation Evaluation Report

## Conclusion

`MULTIMODAL_ABLATION_EVAL_BLOCKED`

- External multimodal count: `0`
- Required external multimodal count: `40`
- Model available: `False`

## Four Required Modes

| Mode | Status |
| --- | --- |
| `text_only` | not executed |
| `image_only` | not executed |
| `text_image` | not executed |
| `text_image_hybrid_rag` | not executed |

## Required Metrics

- `schema_valid_rate`
- `risk_type_accuracy`
- `risk_type_macro_f1`
- `risk_level_accuracy`
- `risk_level_macro_f1`
- `evidence_support_rate`
- `visual_evidence_support_rate`
- `unsupported_claim_rate`
- `visual_unsupported_claim_rate`
- `text_image_consistency_macro_f1`
- `need_human_review_accuracy`
- `human_review_precision`
- `human_review_recall`
- `human_review_f1`
- `high_risk_review_recall`
- `unsafe_auto_pass_rate`
- `fallback_rate`
- `avg_latency_ms`
- `p95_latency_ms`
- `gpu_peak_memory_mb`

## Blocking Reasons

- real multimodal external test set requires at least 40 samples; current=0
- local VLM config, processor/tokenizer, and weights are not available outside Git

## Evidence Boundary

The four-group comparison is intentionally blocked until the same isolated real
multimodal external test set can be evaluated across Text Only, Image Only,
Text+Image, and Text+Image+Hybrid RAG. No synthetic or manually inferred visual
signals are used as a substitute for real VLM output.
