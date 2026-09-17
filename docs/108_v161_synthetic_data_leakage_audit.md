# v1.6.1 模拟数据泄漏审计报告

审计标记：`RAG_LEAKAGE_AUDIT_COMPLETE`

本报告审计 v1.6 合成评论、合成案例和 80 条黄金查询是否存在重复、模板化、查询-案例高重叠以及答案字段/元数据捷径。审计结果用于解释 Hit@3/Hit@5=100% 的可信边界，不覆盖 v1.6 原始评测文件。

## 汇总指标

| 指标 | 数值 |
| --- | ---: |
| exact_duplicate_count | 0 |
| normalized_duplicate_count | 0 |
| near_duplicate_count | 0 |
| suspected_template_family_count | 60 |
| query_case_overlap_mean | 0.152107 |
| query_case_overlap_p95 | 0.290266 |
| high_overlap_query_rate | 0.0125 |
| bge_m3_overlap_mean | 0.707488 |
| bge_m3_overlap_p95 | 0.759562 |
| high_bge_overlap_query_rate | 0.0 |
| metadata_shortcut_count | 109 |
| answer_field_leakage_count | 104 |

## 关键发现

- 完全重复跨集合数量：0；归一化重复跨集合数量：0。
- 高重叠查询数量：1 / 80。
- BGE-M3 cosine 审计：checked=True，mean=0.707488，p95=0.759562。
- 模板家族数量：60。v1.6 数据由固定场景模板生成，该结果说明 100% 检索命中不能直接外推到真实表达。
- 元数据/答案字段捷径数量：109。当前 Oracle 评测路径把期望风险类型/等级作为 request metadata 参与排序，必须新增 No-Oracle 评估。

## 文件产物

- `data/rag/audit/exact_duplicates.jsonl`
- `data/rag/audit/normalized_duplicates.jsonl`
- `data/rag/audit/near_duplicates.jsonl`
- `data/rag/audit/template_families.json`
- `data/rag/audit/high_overlap_queries.jsonl`
- `data/rag/audit/metadata_shortcuts.jsonl`
- `data/rag/audit/leakage_audit_summary.json`

## 结论

v1.6 的 Hybrid RAG 结果可作为工程回归基线，但存在明显的模板数据与 Oracle metadata 评估风险。v1.6.1 后续必须使用 strict 模拟集、真实外部集和 No-Oracle 模式重新评估，不得仅凭原 80 条黄金查询宣布泛化能力。
