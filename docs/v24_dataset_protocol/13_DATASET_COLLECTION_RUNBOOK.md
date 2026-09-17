# 13 数据集收集Runbook

| 步骤 | 输入 | 操作 | 输出 | 质量门禁 |
|---|---|---|---|---|
| 1 | 来源清单 | 建立Source Manifest | source_manifest.jsonl | 来源与许可100%明确 |
| 2 | 合规来源 | 收集候选 | raw_candidates_v0 | 原始记录有Hash |
| 3 | 原始候选 | PII检测与脱敏 | redacted_candidates | 未处理PII=0 |
| 4 | 脱敏候选 | 基础质量筛选 | screened_candidates | 拒绝原因完整 |
| 5 | 筛选候选 | SHA-256精确去重 | exact_dedup_report | exact重复组完整 |
| 6 | 去重候选 | 字符n-gram/Jaccard | lexical_pairs | 候选对可复核 |
| 7 | 去重候选 | BGE-M3语义相似 | semantic_pairs | 模型与阈值版本化 |
| 8 | 候选对 | 人工重复簇复核 | deduplicated_candidates | 决策理由完整 |
| 9 | 去重结果 | 场景与母样本归组 | grouped_candidates | 同组不可跨Split |
| 10 | 分层候选 | 选取Pilot 60 | pilot_60_v0.1 | 覆盖矩阵达标 |
| 11 | Pilot | 双人盲标 | annotations_a/b | 独立标注 |
| 12 | 双标 | 计算一致性 | pilot_metrics | 指标可复现 |
| 13 | 分歧 | 仲裁 | adjudication_log | 未仲裁=0 |
| 14 | Pilot结果 | 修订协议 | dataset-protocol-v1.0 | P0/P1=0 |
| 15 | 正式候选 | 扩大收集与筛选 | formal_candidates | 来源分布达标 |
| 16 | 正式候选 | 标注与复标 | formal_annotations | 双标政策满足 |
| 17 | 标注结果 | Gold Evidence审查 | gold_candidates | Evidence可解析100% |
| 18 | Gold候选 | 污染与跨集检查 | leakage_report | 同组跨Split=0 |
| 19 | 合格候选 | 选取Held-out与Reserve | heldout/reserve | 分层配额达标 |
| 20 | 最终数据 | Gold隔离 | inputs/gold | 运行不可读取Gold |
| 21 | 封存数据 | Hash与Manifest | sealed dataset | Hash完整 |
| 22 | 数据与文档 | Dataset Card | dataset_card.md | 用途与限制明确 |
| 23 | 全部证据 | 只读审计 | final_review | P0/P1=0 |

## 操作责任

每一步至少记录：

- owner；
- reviewer；
- timestamp；
- toolVersion；
- inputHash；
- outputHash；
- exitStatus；
- evidenceFile。

## 失败处理

禁止静默跳过失败。失败状态至少包括：

- BLOCKED_SOURCE_PERMISSION
- BLOCKED_PII
- BLOCKED_SCHEMA
- BLOCKED_DEDUP_REVIEW
- BLOCKED_LOW_AGREEMENT
- BLOCKED_GOLD_EVIDENCE
- BLOCKED_LEAKAGE
- BLOCKED_MANIFEST
