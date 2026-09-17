# 05 筛选协议

每条候选依次经过五道门禁，任何状态变化都要保留审计记录。

## Gate 1 来源门禁

必填：

- sourceType
- sourceRecordHash
- collectionDate
- licenseOrPermission
- allowedUse
- piiStatus

失败状态：

- REJECT_UNKNOWN_SOURCE
- REJECT_PERMISSION_UNCLEAR

## Gate 2 隐私与安全门禁

检查：

- 未脱敏PII；
- API Key、Token、密码；
- 真实订单、支付、快递信息；
- 图片或附件中的个人信息；
- 可执行恶意代码。

失败状态：

- QUARANTINE_PII
- QUARANTINE_SECRET
- REJECT_UNSAFE_CONTENT

## Gate 3 基础质量门禁

通常剔除：

- 纯广告；
- 纯链接；
- 无意义乱码；
- 只有表情且无语义；
- 截断到无法理解；
- 与任务完全无关；
- 无法恢复的机器翻译错误。

通常保留：

- 错别字；
- 口语；
- 方言；
- 反讽；
- 情绪化；
- 极短但语义明确；
- 五星评分却文本投诉；
- 重复Emoji但含有业务事实。

## Gate 4 可标注性门禁

标注者至少应能决定：

- 是否在任务范围内；
- 是否可回答；
- 是否存在风险；
- 是否有可用证据；
- 是否需要人工复核。

不能可靠判断时，优先进入：

- INSUFFICIENT_INFORMATION
- UNANSWERABLE
- AMBIGUOUS
- OUT_OF_SCOPE

不要为了数据“干净”而把困难样本全部删除。

## Gate 5 代表性门禁

每批候选要统计：

- sourceType；
- primaryRiskType候选；
- severity候选；
- 文本长度；
- expressionStyle；
- 商品/场景；
- answerable；
- evidenceAvailability；
- synthetic比例。

出现以下情况需补采或限额：

- 单一来源超过60%；
- 单一模板或场景超过10%；
- 正常样本过少；
- 无答案样本缺失；
- 高风险全部来自合成数据；
- 某类别只存在一种表达方式。

## 筛选记录

每条被拒绝或保留的样本都要记录：

- screeningStatus；
- screeningReasons；
- reviewerId；
- timestamp；
- guidelineVersion；
- previousStatus。
