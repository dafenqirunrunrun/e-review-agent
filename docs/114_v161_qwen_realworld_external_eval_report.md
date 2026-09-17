# v1.6.1 Qwen Real-World External Evaluation Report

## Conclusion

`REALWORLD_QWEN_EXTERNAL_EVAL_BLOCKED`

- Real external text count: `0`
- Required real external text count: `200`
- Input dataset: `data/real_world/external_test/real_reviews_external_test_200.jsonl`

## Compared Modes

- `qwen3_prompt_only`: not executed
- `qwen3_synthetic_rag`: not executed
- `qwen3_real_rag`: not executed
- `qwen3_synthetic_plus_real_hybrid_rag`: not executed

## Required Metrics

- `risk_type_accuracy`
- `risk_type_macro_f1`
- `risk_level_accuracy`
- `risk_level_macro_f1`
- `schema_valid_rate`
- `evidence_support_rate`
- `unsupported_claim_rate`
- `human_review_precision`
- `human_review_recall`
- `high_risk_review_recall`
- `unsafe_auto_pass_rate`
- `fallback_rate`
- `avg_latency_ms`

## Blocking Reasons

- real external text test set requires at least 200 samples; current=0

## Evidence Boundary

This report intentionally does not provide Prompt-only, Synthetic RAG, Real RAG,
or Synthetic+Real Hybrid RAG metrics while the isolated real-world external test
set is unavailable. Synthetic data must not be renamed or reused as real external
evidence.
