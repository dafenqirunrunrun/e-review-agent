# V1.6.5 Schema Source Inventory

Status: `SCHEMA_SOURCE_INVENTORY_COMPLETE`
- canonical_schema_file: `ai-service/app/evaluation/schema_failure_analysis.py`
- canonical_schema_version: `v1.6.5-canonical`
- conflicting_schema_count: `2`

| file | classification | used_by_training | used_by_runtime | used_by_evaluation |
| --- | --- | --- | --- | --- |
| `ai-service/app/evaluation/schema_failure_analysis.py` | `canonical` | `False` | `False` | `True` |
| `ai-service/app/llm/schemas.py` | `legacy` | `False` | `True` | `False` |
| `ai-service/app/llm/qwen_text_runtime.py` | `legacy` | `False` | `True` | `False` |
| `ai-service/scripts/run_v164_controlled_synthetic_qlora_training.py` | `compatible_projection` | `True` | `False` | `False` |
| `ai-service/scripts/eval_v164_synthetic_holdout_and_robustness.py` | `conflicting` | `False` | `False` | `True` |
| `ai-service/scripts/eval_v164_private_real_text_robustness.py` | `conflicting` | `False` | `False` | `True` |
| `ai-service/prompts/json_repair_zh.md` | `legacy` | `False` | `False` | `False` |
