# 01 数据集目标

协议版本：`dataset-protocol-v0.1-draft`

## 1. 项目事实与建议边界

### CURRENT_PROJECT_FACT

当前工程已完成真实Golden Path验证：评论入库、Java调用FastAPI、BGE-M3、FAISS、FlagEmbedding Reranker、Qwen3、Citation、Evidence Bundle、风险任务、人工Override和Trace/Replay均有运行证据。

### PROPOSED_PROTOCOL

数据集不是普通“评论情感分类集”，而是一个多层Agent-RAG评测资产，必须支持：

1. 检索；
2. Reranker；
3. 风险类型；
4. 风险等级；
5. 是否可回答；
6. 证据是否充分；
7. Citation正确性；
8. 是否需要人工复核；
9. 安全治理；
10. 鲁棒性；
11. 运行稳定性。

## 2. 核心评测问题

### Q1 检索

系统能否从固定知识库中召回支持当前风险判断的Chunk？

推荐指标：

- Hit@1 / Hit@3 / Hit@5
- Recall@5
- MRR
- nDCG@5

### Q2 重排

真实FlagEmbedding Reranker能否相对以下路线改善证据排序：

- BM25
- Dense BGE-M3
- Hybrid RRF
- Hybrid＋Deterministic Reranker
- Hybrid＋FlagEmbedding Reranker

比较时除Reranker外其余变量必须固定。

### Q3 风险判断

推荐指标：

- Primary Risk Macro-F1
- Multi-label Micro-F1
- Severity Accuracy / Weighted-F1
- High-risk Recall
- False Positive Rate
- False Negative Rate
- Human Review Routing Accuracy

### Q4 证据与Citation

推荐指标：

- Citation ID Resolvability
- Citation Precision / Recall / F1
- Claim Support Rate
- Evidence Sufficiency
- Hallucinated Citation Rate
- Tenant Violation Rate

### Q5 无答案与拒答

对于信息不足或无相关证据样本，正确行为不是强制输出高风险结论，而是：

- 明确证据不足；
- 不生成虚假Citation；
- 根据策略转人工；
- 不把“相似但无支持”的Chunk当作Gold。

### Q6 安全与鲁棒性

安全子集和鲁棒性子集必须单独报告，不与普通风险Macro-F1混算。

## 3. 数据资产建议

- 历史开发/回归集：预期132条，必须仓库核验；
- Pilot：60条，100%双标；
- 正式Held-out：目标500条；
- Reserve：目标50条；
- 原始候选池：目标约1500条。

## 4. 成功边界

数据集可以支持“在固定代码、模型、索引和500条封存样本上的结果”，但不能支持：

- 对所有电商平台普遍有效；
- 生产级泛化；
- 所有风险类别均具有统计显著优势；
- 大规模公开行业Benchmark。

## 5. 仓库核验项

- 实际风险枚举；
- 实际Evidence Bundle字段；
- 实际Citation粒度；
- 历史132条文件与数量；
- 当前知识库Source/Chunk ID结构；
- 当前是否存在answerable/requiresHumanReview字段。
