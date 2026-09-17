# v1.6 Hybrid RAG 检索评估报告

评估标记：`HYBRID_RAG_EVAL_PASS`

本报告由 80 条黄金查询实际检索生成，检索指标与 Qwen 下游生成指标分开统计。

- 案例数：240
- Embedding：`BAAI/bge-m3`
- bge-m3 本地可用：True
- FAISS 索引可用：True
- Neural reranker 本地可用：True

| 策略 | Hit@1 | Hit@3 | Hit@5 | MRR | nDCG@5 | 空召回率 | 证据覆盖 | 平均延迟(ms) | P95(ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tfidf | 0.9875 | 1.0000 | 1.0000 | 0.9938 | 0.9504 | 0.0000 | 0.7167 | 0.89 | 1.15 |
| dense | 0.8125 | 0.9625 | 0.9750 | 0.8906 | 0.8847 | 0.0000 | 0.7208 | 128.11 | 14.08 |
| hybrid | 0.9000 | 0.9875 | 0.9875 | 0.9437 | 0.9296 | 0.0000 | 0.7542 | 12.23 | 14.12 |
| hybrid_rule | 0.9125 | 1.0000 | 1.0000 | 0.9563 | 0.9425 | 0.0000 | 0.8042 | 12.21 | 15.06 |
| hybrid_neural | 0.9250 | 1.0000 | 1.0000 | 0.9625 | 0.9462 | 0.0000 | 0.7542 | 107.06 | 92.17 |
| hybrid_rerank | 0.9250 | 1.0000 | 1.0000 | 0.9625 | 0.9462 | 0.0000 | 0.7542 | 107.06 | 92.17 |

## 各风险类型 Hit@5

- `tfidf`：after_sales_risk=1.0000, negative_review=1.0000, normal_review=1.0000
- `dense`：after_sales_risk=1.0000, negative_review=1.0000, normal_review=0.8333
- `hybrid`：after_sales_risk=1.0000, negative_review=1.0000, normal_review=0.9167
- `hybrid_rule`：after_sales_risk=1.0000, negative_review=1.0000, normal_review=1.0000
- `hybrid_neural`：after_sales_risk=1.0000, negative_review=1.0000, normal_review=1.0000
- `hybrid_rerank`：after_sales_risk=1.0000, negative_review=1.0000, normal_review=1.0000

## 结论边界

成功门槛为任一完整 Hybrid 策略 Hit@3 >= 0.80、Hit@5 >= 0.90 且空召回率 <= 0.10。
数据为固定种子的合成实验集，结果不代表生产流量，也不能单独证明统计显著性。
