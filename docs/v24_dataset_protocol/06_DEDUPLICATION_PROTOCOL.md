# 06 三级去重协议

## 1. 核心原则

去重不是“相似就删除”，而是区分：

- 真正重复：`duplicateGroupId`
- 同一场景不同表达：`scenarioGroupId`
- 同一母样本生成链：`generationParentId`
- 同一真实事件：`sourceEventId`

## 2. 文本规范化

候选规则：

1. Unicode NFKC；
2. 全半角统一；
3. 英文字母小写；
4. 空格和换行归一；
5. URL、电话、订单号替换为占位符；
6. 重复标点和Emoji适度压缩；
7. 保留影响风险的数字、否定词、时间和程度词；
8. 不删除商品名，除非为隐私或泄漏控制。

任何规范化函数必须版本化：

```text
normalizerVersion=zh-review-normalizer-v0.1
```

## 3. 一级：精确重复

```text
exactHash = SHA-256(normalizedText)
```

Hash相同归入同一`duplicateGroupId`。

代表样本保留顺序：

1. 来源许可最明确；
2. 元数据最完整；
3. 文本信息更完整；
4. 脱敏风险更低；
5. 表达更自然。

## 4. 二级：词面近重复

建议：

- 中文字符3-gram；
- Jaccard；
- 可选MinHash加速；
- 长度比和数字差异先过滤。

Pilot候选阈值：

- Jaccard ≥ 0.92：高度近重复候选；
- 0.80–0.92：人工复核；
- <0.80：通常保留。

阈值不是自动删除规则。

## 5. 三级：语义近重复

使用当前项目已验证的BGE-M3。

Pilot候选阈值：

- Cosine ≥ 0.96：高度语义重复候选；
- 0.90–0.96：人工复核；
- <0.90：通常保留。

以下差异通常要求保留：

- 严重程度不同；
- 时间跨度不同；
- 是否受伤不同；
- 是否退款不同；
- 反讽与直接表达；
- 单风险与复合风险；
- 证据是否充分；
- 是否应转人工不同。

## 6. 跨集合去重

必须比较：

- 新候选内部；
- 新候选 vs 历史合成集；
- 新候选 vs 历史真实集；
- Pilot vs Held-out；
- Held-out vs Reserve；
- 原始评论 vs 人工改写；
- 同一LLM模板生成的多条候选；
- Held-out vs 知识库规则原文。

与知识库主题相关不等于泄漏；直接复制规则问法、答案或证据措辞则需人工审查。

## 7. Group-level Split

同一个`scenarioGroupId`、`sourceEventId`、`generationParentId`或模板家族不得跨Development、Pilot、Held-out、Reserve。

## 8. 去重审核记录

每个重复候选对保存：

- sampleA；
- sampleB；
- exactMatch；
- lexicalScore；
- semanticScore；
- entityDifference；
- numericDifference；
- severityDifference；
- reviewerDecision；
- decisionReason；
- duplicateGroupId；
- scenarioGroupId。
