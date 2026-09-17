# v1.6.1 External Test Isolation Audit

## Conclusion

`EXTERNAL_TEST_ISOLATION_AUDIT_PASS`

This audit statically checks that isolated external test set paths are not referenced by code that could build indexes, train models, tune prompts, select fusion weights, or calibrate thresholds. Allowed references are limited to split generation, evaluation, release-gate reporting, and SFT readiness auditing.

## Allowed References

| File | External-test token |
| --- | --- |
| `ai-service/scripts/audit_external_test_isolation.py` | `data/real_world/external_test`, `data\real_world\external_test`, `multimodal_manifest/real_multimodal_external_test`, `multimodal_manifest\real_multimodal_external_test`, `real_multimodal_external_test.jsonl`, `real_reviews_external_test_200.jsonl`, `real_world/external_test`, `real_world\external_test` |
| `ai-service/scripts/audit_sft_data_readiness.py` | `data/real_world/external_test`, `data\real_world\external_test`, `multimodal_manifest/real_multimodal_external_test`, `multimodal_manifest\real_multimodal_external_test`, `real_multimodal_external_test.jsonl`, `real_reviews_external_test_200.jsonl`, `real_world/external_test`, `real_world\external_test` |
| `ai-service/scripts/build_realworld_split.py` | `data/real_world/external_test`, `data\real_world\external_test`, `real_reviews_external_test_200.jsonl`, `real_world/external_test`, `real_world\external_test` |
| `ai-service/scripts/eval_multimodal_ablation.py` | `real_multimodal_external_test.jsonl` |
| `ai-service/scripts/eval_qwen_realworld_external.py` | `data/real_world/external_test`, `data\real_world\external_test`, `real_reviews_external_test_200.jsonl`, `real_world/external_test`, `real_world\external_test` |
| `ai-service/scripts/eval_rag_validity_and_external.py` | `data/real_world/external_test`, `data\real_world\external_test`, `real_reviews_external_test_200.jsonl`, `real_world/external_test`, `real_world\external_test` |
| `ai-service/scripts/eval_realworld_multimodal_ablation.py` | `real_multimodal_external_test.jsonl` |
| `ai-service/scripts/eval_realworld_vlm_external.py` | `real_multimodal_external_test.jsonl` |
| `ai-service/scripts/eval_vlm_visual_evidence.py` | `real_multimodal_external_test.jsonl` |

## Violations

| File | External-test token | Purpose hint |
| --- | --- | --- |
| - | - | - |

## RAG Index Metadata

| File | External-test token |
| --- | --- |
| - | - |

## Policy

External test sets may be used only for final evaluation and release-gate reporting. They must not be used for indexing, training, prompt selection, fusion-weight tuning, or threshold calibration.
