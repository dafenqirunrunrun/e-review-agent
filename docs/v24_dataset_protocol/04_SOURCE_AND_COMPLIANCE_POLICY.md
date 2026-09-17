# 04 数据来源与合规政策

## 1. 来源类型

| sourceType | 候选池 | Held-out | 人工审核 | 说明 |
|---|---|---|---|---|
| REAL_AUTHORIZED | 允许 | 允许 | 必须 | 已获得明确内部授权 |
| PUBLIC_LICENSED | 允许 | 允许 | 必须 | 许可或公开使用条件明确 |
| HUMAN_REWRITTEN | 允许 | 允许 | 必须 | 基于场景改写，不保留可识别原文 |
| SCENARIO_AUTHORED | 允许 | 允许 | 必须 | 人工设计的业务场景 |
| KNOWLEDGE_GROUNDED_SYNTHETIC | 允许 | 限额 | 必须 | LLM仅生成候选 |
| ROBUSTNESS_TRANSFORMATION | 允许 | 允许 | 必须 | 对已合规母样本生成噪声变体 |
| SECURITY_AUTHORED | 允许 | 允许 | 必须 | 人工设计的注入、PII、越权测试 |
| UNKNOWN | 禁止 | 禁止 | — | 来源不清 |

## 2. 禁止来源

- 未确认许可或用途；
- 直接批量复制受限制平台评论；
- 未授权真实用户数据；
- 包含无法可靠脱敏的个人信息；
- 来源ID、采集日期、许可状态均缺失；
- LLM生成后由同一LLM自动批准为Gold；
- 为了当前系统答对而定向改写的样本；
- 已被用于调试却未标`seenDuringDevelopment=true`的样本。

## 3. 三层文本字段

### rawText

原始文本，只能存放在受控、非Git、访问受限位置。记录路径与Hash，不在仓库中直接保存含PII内容。

### redactedText

用于人工标注的脱敏文本。

### normalizedText

仅用于搜索、Hash和去重；不能覆盖redactedText。

## 4. PII占位符

统一使用：

- `<PHONE>`
- `<ADDRESS>`
- `<ORDER_ID>`
- `<EMAIL>`
- `<PERSON_NAME>`
- `<TRACKING_ID>`
- `<PAYMENT_ID>`
- `<ACCOUNT_ID>`

数字信息若影响风险判断必须保留，例如“拖延3天”和“拖延30天”不能统一。

## 5. 合成候选

合成样本必须记录：

- generatorModel；
- generatorPromptVersion；
- generationSeed；
- scenarioTemplateId；
- generationParentId；
- humanReviewed；
- humanAccepted；
- syntheticReason。

建议正式Held-out中合成或受控改写样本占比不超过25%，最终比例由Pilot和来源可得性决定。

## 6. 公开边界

在来源、平台条款和授权未确认前，数据集默认：

```text
INTERNAL_EVALUATION_ONLY
```

不得默认公开原始文本。
