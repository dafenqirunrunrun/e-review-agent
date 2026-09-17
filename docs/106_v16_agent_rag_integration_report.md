# v1.6 Agent 与 Hybrid RAG 接入报告

## 1. Agent 流程

流程为：评论输入、规则初判、检索查询、Hybrid RAG、证据充分性判断、Top-K 案例注入 Qwen3、JSON Schema 校验、人工复核路由和评估反馈。`E_REVIEW_RAG_V2_ENABLED=false` 为兼容默认值，因此 v1.5.1 Prompt-only 路径保持不变。

Prompt 新增 `retrieved_cases`、`retrieval_strategy`、`evidence_count` 和 `retrieval_confidence`。案例字段显式命名为 historical risk/evidence，模型被要求仅从当前评论和当前图片填写 evidence。

## 2. 路由规则

- high risk 必须人工复核；
- medium risk 且 Top 分数低于 0.35 时人工复核；
- 当前证据为空时人工复核；
- 检索工具失败时 fallback 并人工复核；
- low risk、置信度不低于 0.75 且证据充分时进入普通运营建议。

响应记录 route_decision、route_reason、evidence_sufficient 和 human_review_trigger。该路由只决定建议流向，不执行真实业务动作。

## 3. 可观测性

Agent Run 记录 rag_enabled、策略、命中数、Top 分数、Embedding、reranker、检索延迟和路由结果。Agent Step/Tool Log 使用 `HybridRagRetrieverTool`、`RerankerTool` 和 `EvidenceSufficiencyTool`，记录候选/命中数量、案例 ID、分数摘要、耗时与错误，不保存完整敏感评论。

## 4. 接口与页面

FastAPI 的 RAG v2 接口经 admin-api 的 Shiro 鉴权代理暴露给管理端。RAG 质量页面显示模型/索引状态、Hit@K、MRR、nDCG、空召回率、Top-K 分数拆解、失败查询和 Prompt-only/RAG 下游对比。Agent Trace 同步显示 Run 级 RAG 数据和三个检索步骤。

## 5. 验证结论

- 80 条黄金查询的真实检索评估标记为 `HYBRID_RAG_EVAL_PASS`。Hybrid + NeuralReranker 的 Hit@3、Hit@5 均为 1.0000，MRR 为 0.9625，nDCG@5 为 0.9462，空召回率为 0。
- 下游四组各执行 100 条本地 Qwen3 推理，共 400 次。Prompt-only 风险类型/等级准确率为 84%，Hybrid + NeuralReranker 为 88%，Schema、字段完整、证据支持和本地模型成功率均为 100%，fallback 与无依据声明率均为 0。
- Hybrid 组的人工复核判断准确率为 76%，低于 Prompt-only 的 92%；该退化已保留在报告中，说明路由阈值仍需在真实数据上校准，不能仅依据风险分类准确率决定默认启用。
- `litemall_ai_agent_run` 的 RAG 字段迁移已重复执行验证，Agent Run、Step 与 Tool Log 可记录策略、模型、命中案例、分数摘要、检索耗时和路由结论。日志不保存完整评论正文。
- 本次结果基于固定合成数据集和单机本地模型，支持工程验收与消融对比，不构成生产流量上的统计显著性结论。RAG v2 默认关闭，v1.5.1 Prompt-only 路径保持兼容。
