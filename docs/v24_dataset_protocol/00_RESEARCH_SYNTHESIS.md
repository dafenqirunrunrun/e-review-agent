# 00 公开案例调研与共同经验

## 1. 调研范围

本协议综合了 RAG、检索、证据标注、无答案评测、数据去重、数据说明书和泄漏防控等公开案例。研究目的不是机械复制某个 Benchmark，而是抽取能适配电商评论治理 Agent-RAG 的共同流程。

## 2. 主要案例与可借鉴经验

### MIRACL：自动规则检查与人工复核并行

MIRACL 在18种语言中构建大规模检索相关性判断，除母语标注外，还执行自动启发式检查和人工质量评估。对本项目的启示是：字段完整性、ID有效性、重复检查等交给程序；风险边界、证据充分性、近重复簇则必须人工复核。[S1]

### NoMIRACL：必须同时建设“有相关证据”和“无相关证据”子集

NoMIRACL把样本明确拆成 relevant 与 non-relevant 两组，并分别测无证据时的幻觉倾向和有证据时的识别错误。对本项目的启示是：不能只收“系统应该能判断”的评论，还要收信息不足、知识库无相关规则、正常评论和不应强行引用的样本。[S2]

### GaRAGe：逐段标注支持证据，并要求无充分依据时回避

GaRAGe包含人工整理答案和逐个 grounding passage 的相关性标注，能够分别评估证据选择、事实支持和无证据回避。对本项目的启示是：每条核心样本应支持 Chunk 级 Gold Evidence，不能只标风险类别。[S3]

### RAGTruth：案例级与细粒度支持性标注

RAGTruth对RAG生成结果进行案例级和词级人工标注，说明只看最终分类正确不足以评价生成内容是否有未被证据支持的部分。对本项目的启示是：Citation 可解析不等于结论被支持，应单独标 Claim Support 和 Evidence Sufficiency。[S4]

### CRAG：按领域、问题类型、长尾程度、动态性和复杂度分层

CRAG不是随机搜集问答，而是按多领域、多问题类型、实体流行度和时间动态性组织样本。对本项目的启示是：候选池要按风险类型、严重程度、表达方式、证据状态、商品/业务场景分层，避免单一投诉模板占据多数。[S5]

### SemDeDup：精确去重之外还要做语义去重

SemDeDup使用预训练模型Embedding识别词面不同但语义重复的样本。对本项目的启示是：SHA-256只能删除完全重复，还要通过字符n-gram和BGE-M3发现复制改写、模板化投诉和同义近重复。[S6]

### SMART Filtering：低信息量、污染和Embedding近重复都应筛查

SMART Filtering同时移除过易、受污染和Embedding空间相近的样本，强调较小但有区分度的数据集优于大量重复低质量数据。对本项目的启示是：候选池筛选不能只追求数量，还要审查样本是否真正能区分不同检索和Reranker方案。[S7]

### Datasheets / Data Statements：从一开始记录动机、组成、来源、限制和适用范围

Datasheets与Data Statements强调数据集必须有系统化文档，说明收集动机、组成、过程、推荐用途、限制、语言和人群覆盖。对本项目的启示是：Dataset Card、Source Manifest和版本历史不是最后补写，而应贯穿收集过程。[S8][S9]

### 数据污染研究：测试样本或其近似版本进入开发过程会虚高结果

公开研究指出，测试集直接泄漏、合成近似泄漏和使用测试集进行模型选择都会导致评测高估。对本项目的启示是：同一事件、母样本、模板家族和改写必须按组切分；任何用于调Prompt、知识库、阈值或Reranker选择的样本都要移出严格Held-out。[S10][S11]

### 专业裁决类Benchmark：事实、政策证据、最终决定应可追踪

InsLogicBench等专业裁决任务将事实、相关政策条款和最终结论连接起来，并进行一致性验证。电商评论治理同样属于“事实描述—规则证据—风险判断—人工处置”的链路，因此样本应保存证据和裁决理由，而不是只保留一个标签。[S12]

## 3. 共同流程结论

综合案例后，本项目采用以下标准流程：

```text
任务定义
→ 项目字段盘点
→ 风险本体
→ 来源与合规
→ 候选池分层收集
→ PII脱敏
→ 基础质量筛选
→ 精确/词面/语义三级去重
→ 场景组归并
→ 60条双人试标
→ 一致性与分歧分析
→ 协议修订并升至v1.0
→ 正式候选扩充
→ 标注/复标/仲裁
→ 跨集污染检查
→ Gold隔离
→ Dataset Manifest与Dataset Card
→ 封存Held-out
```

## 4. 本研究包的边界

- 本包不会虚构仓库中实际存在的风险枚举；
- 历史“80条合成＋52条真实”目前仅作为待核验资产；
- 去重阈值是Pilot候选值，不是最终固定阈值；
- 500条Held-out、60条Pilot和约1500条候选池是项目建议，不是论文规定；
- 本包不收集真实评论，不写入PII，不生成正式Gold数据。

## 5. 参考文献

- [S1] Zhang et al. MIRACL: A Multilingual Retrieval Dataset Covering 18 Diverse Languages. TACL 2023.
- [S2] Thakur et al. “Knowing When You Don’t Know”: NoMIRACL. Findings of EMNLP 2024.
- [S3] Sorodoc et al. GaRAGe: A Benchmark with Grounding Annotations for RAG Evaluation. Findings of ACL 2025.
- [S4] Niu et al. RAGTruth. ACL 2024.
- [S5] Yang et al. CRAG — Comprehensive RAG Benchmark. 2024.
- [S6] Abbas et al. SemDeDup. 2023.
- [S7] Gupta et al. SMART Filtering. NAACL 2025.
- [S8] Gebru et al. Datasheets for Datasets. 2018/2021.
- [S9] Bender and Friedman. Data Statements for NLP. TACL 2018.
- [S10] Sainz et al. NLP Evaluation in Trouble: Data Contamination. Findings of EMNLP 2023.
- [S11] Matton et al. On Leakage of Code Generation Evaluation Datasets. Findings of EMNLP 2024.
- [S12] Liu et al. InsLogicBench. ACL 2026.
