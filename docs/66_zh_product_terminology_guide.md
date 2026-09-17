# v1.1.1 中文产品术语规范

## 使用原则

- UI、PPT 和答辩文档优先使用中文表达。
- API 路径、数据库字段、JSON 字段、枚举存储值保持英文，不在后端或数据库层改名。
- 英文缩写只在必要时保留，并在首次出现时用中文解释。
- 避免在页面上裸露 `pending`、`approved`、`undefined`、`null`、`NaN` 等工程词。

## 状态术语

| English | 推荐中文 | 保留缩写 | 使用场景 | 禁用说法 |
| --- | --- | --- | --- | --- |
| pending | 待处理 / 待分析 / 待审批 | 否 | 任务、评论、审批状态 | pending |
| approved | 已批准 | 否 | 工具审批 | approved |
| rejected | 已拒绝 | 否 | 工具审批 | rejected |
| enabled | 已启用 | 否 | 开关状态 | enabled |
| disabled | 已停用 | 否 | 开关状态 | disabled |
| success | 成功 | 否 | 运行、构建、巡检 | success |
| failed | 失败 | 否 | 运行、构建、巡检 | failed |
| running | 运行中 | 否 | 智能体状态 | running |
| completed | 已完成 | 否 | 任务完成 | completed |
| blocked | 已阻断 | 否 | 安全护栏 | blocked |
| warning | 警告 / 需关注 | 否 | 诊断提示 | warning |
| unknown | 未知 | 否 | 无状态 | unknown |
| active | 生效中 | 否 | 策略状态 | active |
| inactive | 未生效 | 否 | 策略状态 | inactive |

## 风险等级

| English | 推荐中文 | 保留缩写 | 使用场景 | 禁用说法 |
| --- | --- | --- | --- | --- |
| low | 低风险 | 否 | 风险等级标签 | low |
| medium | 中风险 | 否 | 风险等级标签 | medium |
| high | 高风险 | 否 | 风险等级标签 | high |
| critical | 严重风险 | 否 | 高危事件 | critical |

## 情感与反馈

| English | 推荐中文 | 保留缩写 | 使用场景 | 禁用说法 |
| --- | --- | --- | --- | --- |
| positive | 正向 | 否 | 情感标签 | positive |
| neutral | 中性 | 否 | 情感标签 | neutral |
| negative | 负向 | 否 | 情感标签 | negative |
| accept | 采纳建议 | 否 | 人工反馈 | accept |
| false_positive | 误报 | 否 | 人工反馈 | false_positive |
| risk_level_too_high | 风险等级偏高 | 否 | 人工反馈 | risk_level_too_high |
| risk_level_too_low | 风险等级偏低 | 否 | 人工反馈 | risk_level_too_low |
| suggestion_bad | 建议不适用 | 否 | 人工反馈 | suggestion_bad |
| transferred_after_sales | 已转售后处理 | 否 | 人工反馈 | transferred_after_sales |
| closed_without_action | 无需处理并关闭 | 否 | 人工反馈 | closed_without_action |

## 智能体平台术语

| English | 推荐中文 | 保留缩写 | 使用场景 | 禁用说法 |
| --- | --- | --- | --- | --- |
| Agent Trace | 执行追踪 | 可保留 Agent | 菜单、页面标题 | Trace |
| Agent Run | 智能体运行 | 可保留 Agent | 运行记录 | run |
| Agent Step | 智能体步骤 | 可保留 Agent | 步骤列表 | step |
| Replay | 重放 | 否 | 历史运行重放 | replay |
| Compare | 对比 | 否 | 结果对比 | compare |
| State Snapshot | 状态快照 | 否 | 运行状态 | snapshot |
| Tool Call | 工具调用 | 否 | 执行日志 | tool call |
| Tool Registry | 工具注册中心 | 否 | 菜单、页面 | tool registry |
| Tool Approval | 工具审批 | 否 | 审批流程 | approval |
| Tool Policy | 工具策略 | 否 | 权限配置 | policy |
| Guardrails | 安全护栏 | 否 | 菜单、页面 | guardrail |
| Memory Center | 记忆中心 | 否 | 菜单、页面 | memory |
| AgentOps | 智能体运维 | 可保留 AgentOps | 菜单、指标页 | agentops |
| Agent Registry | 智能体注册中心 | 否 | 菜单、页面 | registry |
| Case Knowledge | 案例知识库 | 否 | 菜单、页面 | knowledge |
| RAG Quality | RAG 质量评估 | 保留 RAG | 菜单、页面 | rag quality |
| HITL | 人工介入 / 人机协同 | 首次解释后可保留 | 论文、答辩 | hitl |
| Fallback | 回退机制 | 否 | 框架状态、评估 | fallback |
| Framework Status | 框架状态 | 否 | 配置页 | framework |
| Diagnostics | 诊断中心 | 否 | 评估、排障 | diagnostics |

## 智能体角色

| English | 推荐中文 | 保留缩写 | 使用场景 | 禁用说法 |
| --- | --- | --- | --- | --- |
| Review Analyst Agent | 评论分析智能体 | 可保留 Agent | 角色说明 | analyst |
| Risk Auditor Agent | 风险审查智能体 | 可保留 Agent | 角色说明 | auditor |
| Case Retriever Agent | 案例检索智能体 | 可保留 Agent | 角色说明 | retriever |
| Operation Advisor Agent | 运营建议智能体 | 可保留 Agent | 角色说明 | advisor |

## H5 演示用语

| 场景 | 推荐中文 | 禁用说法 |
| --- | --- | --- |
| 演示支付 | 演示支付成功（不调用真实支付） | mock pay |
| 演示发货 | 演示发货 | mock ship |
| 评价提交 | 评价提交成功，后台智能体将自动巡检分析 | AI Agent raw text |
| 库存不足 | 当前库存不足，无法提交订单 | undefined / null |
| 演示商品 | E-Review 示例商品 | demo product |
## v1.2 新增术语

| 技术术语 | 页面展示建议 |
| --- | --- |
| Tool Manifest | 工具协议清单 |
| OpenAPI-like | OpenAPI 风格描述 |
| MCP-like | 本地 MCP 风格描述 |
| Schema | 输入输出结构 |
| Contract Test | 契约测试 |
| Retrieval Failure | 检索失败样本 |
| Empty Retrieval | 空召回 |
| AgentOps Trend | 智能体运维趋势 |

说明：本地 MCP 风格描述只表示本地 JSON 工具定义，不表示已经接入外部 MCP 服务。
