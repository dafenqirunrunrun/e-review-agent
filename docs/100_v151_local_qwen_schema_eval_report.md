# v1.5.1 本地 Qwen3 JSON Schema 评估报告

评估标记：`LOCAL_QWEN_SCHEMA_EVAL_PASS`

本报告由实际脚本调用本地 FastAPI Provider 生成，不把 fallback 结果计入 Qwen3 成功率。

- 接口：`http://127.0.0.1:8010/api/v1/llm/review/analyze`
- 模型：`Qwen/Qwen3-1.7B`
- 测试集规模：100 条
- 实际完成评估：100 条
- 阻塞原因：`无`
- 风险、证据与无依据声明指标只以真实本地 Qwen 成功样本为分母；fallback 单独统计

| 指标 | 结果 | 初始门槛 |
| --- | ---: | ---: |
| schema_valid_rate | 100.00% | >= 90% |
| field_complete_rate | 100.00% | >= 90% |
| risk_type_accuracy | 84.00% | 记录值 |
| risk_level_accuracy | 84.00% | 记录值 |
| evidence_support_rate | 100.00% | 记录值 |
| unsupported_claim_rate | 0.00% | <= 15% |
| fallback_rate | 0.00% | 记录值 |
| local_qwen_success_rate | 100.00% | >= 80% |
| avg_latency_ms | 2825.88 ms | 记录值 |
| p95_latency_ms | 3217.00 ms | 记录值 |
| invalid_json_count | 0 | 记录值 |
| repair_used_rate | 0.00% | 记录值 |

结果只代表本机、当前模型权重、Prompt 和 100 条测试集，不代表生产级模型质量。
