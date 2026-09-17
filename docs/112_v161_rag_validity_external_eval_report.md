# v1.6.1 RAG 有效性与真实外部评估报告

结论：`REALWORLD_EXTERNAL_EVAL_BLOCKED`

本报告同时记录 v1.6 原始 Oracle、v1.6 原始 No-Oracle、v1.6.1 strict No-Oracle 和真实外部集状态。核心结论优先看 No-Oracle；真实外部数据缺失时不得报告 PASS。

## 数据规模

- 原始模拟查询：80
- strict 模拟查询：80
- 真实外部文本：0

## Hybrid Neural 对比

| 数据/模式 | Hit@3 / Hit@5 / MRR | 说明 |
| --- | ---: | --- |
| original_oracle | 1.0000 / 1.0000 / 0.9625 | v1.6 原 evaluator，含 expected risk metadata |
| original_no_oracle | 0.9875 / 1.0000 / 0.9531 | 只输入 query_text 与 product_category |
| strict_no_oracle | 0.2125 / 0.3250 / 0.1821 | strict 改写查询，不含答案字段 |

## 结论边界

- 原始 Oracle 指标用于回归，不用于泛化结论。
- strict No-Oracle 用于暴露模板和元数据捷径影响；不要求保持 100%。
- 真实外部文本集尚未准备完成，因此 `REALWORLD_EXTERNAL_EVAL_PASS` 仍为 BLOCKED。
