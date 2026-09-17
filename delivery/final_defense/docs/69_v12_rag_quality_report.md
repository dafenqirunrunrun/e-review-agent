# v1.2 RAG 检索质量评估报告

本报告评估本地关键词、风险类型、混合检索和轻量 TF-IDF 检索效果。系统未接入外部向量数据库，未接入 Qdrant，未下载外部模型。

## 指标汇总

| 指标 | 数值 |
| --- | ---: |
| query_count | 40 |
| retrieval_hit_rate | 97.5 |
| top1_expected_match_rate | 92.5 |
| top3_expected_match_rate | 97.5 |
| empty_retrieval_rate | 2.5 |
| evidence_coverage_rate | 100.0 |
| operation_result_coverage | 90.0 |
| avg_match_score | 0.9096 |
| avg_latency_ms | 0.022 |
| keyword_hit_rate | 100.0 |
| risk_type_hit_rate | 100.0 |
| hybrid_hit_rate | 97.5 |
| tfidf_hit_rate | 97.5 |
| recommended_strategy_win_rate | 97.5 |
| failed_query_count | 1 |

## 策略表现

| 策略 | 命中率 | 首条匹配率 |
| --- | ---: | ---: |
| keyword | 100.0 | 85.0 |
| risk_type | 100.0 | 85.0 |
| hybrid | 97.5 | 92.5 |
| tfidf | 97.5 | 92.5 |

## 低分或失败样本

| 查询ID | 期望风险 | 混合检索首条 | 分数 | 是否前三命中 |
| --- | --- | --- | ---: | --- |
| RAG040 | none | rating_text_conflict | 0.2118 | False |

## 失败原因归类

- 空召回：查询缺少与本地案例风险词表重叠的关键词。
- 低分召回：命中方向正确，但证据片段覆盖不足。
- 风险类型混淆：售后、质量和描述不符在短文本中可能同时出现，需要结合商品上下文。

## 改进建议

- 继续沉淀真实用户端评价到案例知识库。
- 对低分样本补充运营处理结果和证据片段。
- 后续如进入生产化，可评估标准向量检索；当前 v1.2 明确不接外部向量数据库。

RAG_QUALITY_CHECK_PASS