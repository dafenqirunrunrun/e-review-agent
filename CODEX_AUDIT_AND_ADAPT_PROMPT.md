# Codex：E-Review数据集协议仓库适配与独立审核

你收到的是一套经过公开Benchmark调研形成的研究版协议包。它不是最终项目事实，必须在真实仓库中完成代码级适配。

## 工作目录

```text
D:\EReviewAgent\litemall-v24-dataset-protocol
```

基线：

```text
d8a3ebbc
```

目标目录：

```text
docs/v24_dataset_protocol
```

## 第一原则

必须严格区分：

- CURRENT_PROJECT_FACT
- RESEARCH_COMMON_PRACTICE
- PROPOSED_PROTOCOL
- REPOSITORY_VERIFICATION_REQUIRED

不得把建议规则冒充项目已有实现。

## 任务1：盘点项目真实字段

搜索Java、Python、数据库、前端、Prompt和Golden Path报告，确认：

1. 风险类型枚举；
2. 风险等级；
3. AI分析表字段；
4. 风险任务字段；
5. requiresHumanReview；
6. answerable；
7. Citation；
8. Evidence Bundle；
9. Source/Chunk/Tenant ID；
10. 多标签持久化；
11. Override字段；
12. 当前Prompt输出Schema。

输出字段映射矩阵，所有冲突必须解决或显式映射。

## 任务2：盘点历史80＋52数据

找到实际文件，统计：

- 路径；
- SHA-256；
- 实际数量；
- 字段；
- 重复；
- Gold Evidence；
- 历史用途；
- 是否用于调参；
- 推荐角色。

不得只根据旧报告填写80和52。

## 任务3：适配风险本体

以代码真实canonical code为主，更新：

- schema/risk_ontology_v0.1.json；
- 03_RISK_ONTOLOGY.md；
- Annotation Schema；
- Decision Log。

如Java、Python、数据库和前端不一致，建立显式映射，不得静默选择一套。

## 任务4：适配Evidence/Citation

从实际Agent-RAG响应与Evidence Bundle确定：

- Gold粒度；
- ID格式；
- Citation解析；
- Tenant；
- Rerank元数据；
- indexVersion；
- 无证据行为。

更新08文档和Schema。

## 任务5：运行并修复Schema

```powershell
$PY = "D:\anaconda\envs\ereview-v24-transformers451\python.exe"
& $PY -m pip install -r docs\v24_dataset_protocol\requirements-protocol-tools.txt
& $PY docs\v24_dataset_protocol\scripts\validate_protocol_schemas.py
& $PY docs\v24_dataset_protocol\scripts\check_protocol_consistency.py
& $PY docs\v24_dataset_protocol\scripts\check_required_terms.py
```

所有脚本必须PASS。

## 任务6：独立审核

切换为独立Reviewer角色，至少推演15_PROTOCOL_REVIEW_REPORT.md中的20个案例。

对每个案例记录：

- 输入；
- 协议决定；
- 适用规则；
- 是否唯一；
- 问题等级；
- 修订；
- 最终状态。

审核：

- 项目一致性；
- 跨文档一致性；
- Schema一致性；
- 泄漏防控；
- 可执行性；
- PII与来源；
- 去重误删风险；
- Gold Evidence可操作性。

## 任务7：关闭P0/P1

允许状态：

- P0=0
- P1=0
- P2≤5
- P3可保留

只要P1未关闭：

```text
readyForPilot60Collection=false
```

## 任务8：更新结论

更新：

- 15_PROTOCOL_REVIEW_REPORT.md
- 16_PILOT_READINESS.md
- 17_EXECUTIVE_SUMMARY.md
- dataset_protocol_validation.json

正常目标：

```text
classification=PASS_WITH_WARNINGS
readyForPilot60Collection=true
readyForFormal500Collection=false
readyForEvaluation=false
datasetCollectionStarted=false
formalSamplesCreated=0
```

阈值需要Pilot校准属于Warning，不属于P1。

## 禁止

- 不收集正式数据；
- 不生成60条Pilot；
- 不生成500条；
- 不抓取平台评论；
- 不读取或提交真实PII；
- 不修改Prompt、模型、索引和业务逻辑；
- 不Push、Tag、Release；
- 不把建议写成当前实现。

## 提交

只提交协议、Schema、审核报告和验证脚本：

```text
docs: define and audit v2.4 dataset protocol v0.1
```

结束时输出：

- Worktree/Branch/Commit；
- 历史资产实际数量；
- 风险字段映射；
- Evidence粒度；
- Schema验证；
- 20个边界案例结果；
- P0/P1/P2/P3；
- Pilot readiness；
- 新Commit；
- 工作区状态。
