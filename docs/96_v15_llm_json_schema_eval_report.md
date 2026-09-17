# v1.5 LLM JSON Schema 评估报告

评估标记：`LLM_SCHEMA_EVAL_PASS`

本报告由 `ai-service/scripts/eval_llm_schema.py` 对实际运行中的 FastAPI 接口生成，不包含人工填写或伪造指标。

- 接口：`http://127.0.0.1:8008/api/v1/llm/review/analyze`
- 测试集：`data/eval/review_schema_eval.jsonl`（100 条）
- 当前评估模式：未配置真实 API Key 时自动使用 `local_rule_fallback`

| 指标 | 结果 | 初始门槛 |
| --- | ---: | ---: |
| schema_valid_rate | 100.00% | >= 95% |
| field_complete_rate | 100.00% | >= 95% |
| risk_type_accuracy | 100.00% | 记录值 |
| risk_level_accuracy | 100.00% | 记录值 |
| evidence_support_rate | 100.00% | 记录值 |
| unsupported_claim_rate | 0.00% | <= 10% |
| fallback_rate | 100.00% | 记录值 |
| avg_latency_ms | 2.32 ms | 记录值 |

说明：该结果只反映当前 100 条小型测试集及当前 Provider 配置，不代表生产级模型效果。Qwen/DeepSeek 未配置 Key 时，不报告其真实模型质量。
