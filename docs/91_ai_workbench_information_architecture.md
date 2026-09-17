# v1.4 AI 工作台信息架构

## 新的 5 个一级入口

| 一级入口 | 路由 | 定位 | 聚合能力 |
| --- | --- | --- | --- |
| 智能治理首页 | /ai-workbench/home | 业务概览、演示引导、最近任务 | Dashboard 摘要、主流程按钮、最近风险、最近运行 |
| 评论治理流程 | /ai-workbench/governance-flow | 主业务闭环 | 商品评论、智能体巡检、风险任务、运营处理 |
| 运行观测与评估 | /ai-workbench/observability | 智能体可观测性 | 执行追踪、重放对比、评估中心、AgentOps、失败诊断 |
| 知识增强与质量 | /ai-workbench/knowledge-quality | 检索增强与证据质量 | 案例知识库、RAG 质量、本地记忆 |
| 平台治理设置 | /ai-workbench/platform-governance | 高级平台治理能力 | 工具管理、审批策略、安全护栏、智能体注册、配置中心 |

## 旧路由兼容策略

| 旧路由 | 处理方式 |
| --- | --- |
| /ai-workbench/dashboard | 重定向到 /ai-workbench/home |
| /ai-workbench/patrol | 重定向到 /ai-workbench/governance-flow?tab=patrol |
| /ai-workbench/risk | 重定向到 /ai-workbench/governance-flow?tab=risk |
| /ai-workbench/operation | 重定向到 /ai-workbench/governance-flow?tab=operation |
| /ai-workbench/agent-trace | 重定向到 /ai-workbench/observability?tab=trace |
| /ai-workbench/agent-eval | 重定向到 /ai-workbench/observability?tab=eval |
| /ai-workbench/agentops | 重定向到 /ai-workbench/observability?tab=agentops |
| /ai-workbench/case-knowledge | 重定向到 /ai-workbench/knowledge-quality?tab=case |
| /ai-workbench/rag-quality | 重定向到 /ai-workbench/knowledge-quality?tab=rag |
| /ai-workbench/memory-center | 重定向到 /ai-workbench/knowledge-quality?tab=memory |
| /ai-workbench/tool-registry | 重定向到 /ai-workbench/platform-governance?tab=tools |
| /ai-workbench/guardrails | 重定向到 /ai-workbench/platform-governance?tab=guardrails |
| /ai-workbench/agent-registry | 重定向到 /ai-workbench/platform-governance?tab=agents |
| /ai-workbench/config | 重定向到 /ai-workbench/platform-governance?tab=config |

评价分析和模拟评论提交作为备用演示能力保留旧页面，不作为主菜单展示。

## 不进入后台菜单的能力

答辩前服务检查、最终验收、数据库备份恢复、交付包生成属于交付流程，不属于系统业务 UI。它们继续由脚本、文档和 delivery/final_defense 目录承载。

## 用户理解路径

用户进入 AI 工作台后，优先看到智能治理首页；首页解释系统用途，并提供 5 步演示按钮。用户可以在 30 秒内理解系统面向“电商图文评论治理”，在 5 分钟内沿“提交评价 -> 巡检 -> 风险 -> 运营 -> 追踪评估”完成一次演示。
