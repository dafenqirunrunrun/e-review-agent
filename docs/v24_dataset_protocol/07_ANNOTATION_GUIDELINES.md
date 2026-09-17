# 07 人工标注指南

## 1. 独立盲标原则

首次标注时不得展示：

- 当前模型预测；
- 检索TopK；
- Reranker分数；
- Prompt输出；
- 其他标注者标签；
- 历史最终裁决。

标注者可以查看固定知识库和规则文档，用于Gold Evidence判断。

## 2. 固定标注顺序

1. `inScope`
2. `containsPII`
3. `containsPromptInjection`
4. `answerable`
5. `hasRisk`
6. `primaryRiskType`
7. `secondaryRiskTypes`
8. `severity`
9. `evidenceAvailability`
10. `goldEvidenceIds`
11. `requiresHumanReview`
12. `expressionStyle`
13. `robustnessTags`
14. `ambiguity`
15. `annotationRationale`

## 3. 关键负类区分

### NO_RISK

文本语义清楚，没有需要治理的风险。

### INSUFFICIENT_INFORMATION

文本表达可能负面，但信息不足以可靠判断具体风险。

示例：“东西不好。”

### UNANSWERABLE / NO_RELEVANT_EVIDENCE

评论信息可能明确，但当前知识库没有足够规则证据支撑结论。

### OUT_OF_SCOPE

不属于电商评论治理任务。

## 4. 风险等级

风险等级由业务事实和规则决定，不由模型置信度决定。

- LOW：轻微、证据弱、常规处理；
- MEDIUM：明确权益或履约问题，通常需人工；
- HIGH：安全、重大欺诈、群体性影响或需立即升级。

## 5. 人工复核标签

以下情况默认`requiresHumanReview=true`：

- HIGH；
- PRODUCT_SAFETY；
- 多风险；
- 证据冲突；
- 严重但信息不完整；
- 安全注入或PII；
- 主标签存在合理歧义；
- 规则要求人工审批。

## 6. 标注理由

理由应简短、可审计，必须说明：

- 哪段文本事实触发标签；
- 哪条证据支持；
- 为什么主标签优先；
- 为什么需要或不需要人工复核。

不得写模型内部推理或不可验证猜测。

## 7. 不确定处理

标注者不得通过猜测强行完成。应使用：

- ambiguity=true；
- requiresAdjudication=true；
- uncertaintyReason；
- candidateAlternativeLabels。

## 8. 版本

每条标注记录：

- annotatorId；
- guidelineVersion；
- annotationTimestamp；
- toolVersion；
- independent=true/false。
