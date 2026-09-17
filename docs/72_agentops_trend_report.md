# 智能体运维趋势报告

## 目标

智能体运维趋势用于说明系统不仅能完成单次 AI 评论治理，还能观察运行质量、失败类型、工具失败、本地回退、护栏事件、RAG 命中率和质量评分变化。

## 数据来源

- 智能体运行记录。
- 智能体步骤记录。
- 工具执行日志。
- 安全护栏事件。
- 案例检索日志。
- 人工反馈和重放记录。

## 接口范围

- `GET /admin/ai/agentops/trends?range=7d`
- `GET /admin/ai/agentops/recent-runs?limit=20`
- `GET /admin/ai/agentops/failure-top`
- `GET /admin/ai/agentops/tool-failure-top`
- `GET /admin/ai/agentops/fallback-distribution`
- `GET /admin/ai/agentops/guardrail-trend`
- `GET /admin/ai/agentops/rag-trend`
- `GET /admin/ai/agentops/quality-trend`

## 页面展示

后台智能体运维页展示最近 7 天趋势、最近 20 次运行、失败类型 Top5、工具失败 Top5、本地回退分布和质量趋势。历史数据不足时显示友好空状态。

## 验收

趋势检查脚本会检查所有趋势接口，成功输出 `AGENTOPS_TREND_CHECK_PASS`。
