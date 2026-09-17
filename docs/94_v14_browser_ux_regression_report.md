# v1.4 浏览器 UX 回归报告

## 检查范围

本报告用于记录 v1.4 AI 工作台产品体验收口后的浏览器检查项。检查目标是确认 5 个新入口可访问、旧路由兼容、H5 演示链路仍可展示。

## 实际检查页面

| 页面 | 路由 | 检查重点 | 结论 |
| --- | --- | --- | --- |
| AI 工作台首页 | /ai-workbench/home | 说明卡片、指标、5 步演示按钮 | PASS |
| 评论治理流程 | /ai-workbench/governance-flow | 真实评价、巡检、风险、运营 Tab | PASS |
| 运行观测与评估 | /ai-workbench/observability | Trace、Replay、Eval、AgentOps、Diagnostics | PASS |
| 知识增强与质量 | /ai-workbench/knowledge-quality | 案例、检索质量、本地记忆 | PASS |
| 平台治理设置 | /ai-workbench/platform-governance | 工具、安全护栏、智能体注册、配置 | PASS |
| H5 商品详情 | /items/detail/1181000 | 演示评价治理提示、金额正常 | PASS |
| H5 支付页 | /order/payment | 演示支付说明、不出现 NaN | PASS |
| H5 评价提交 | /order/comment?orderId=61&orderGoodsId=61 | 进入后台智能治理说明 | PASS |

## 验收标记

浏览器真实检查已完成，输出：

```text
V14_BROWSER_UX_REGRESSION_PASS
```

## 当前说明

v1.4 的浏览器检查聚焦产品体验，不新增真实支付、真实物流、真实退款、外部 MCP 或 Qdrant。

## 检查记录

- 检查时间：2026-07-01。
- 检查方式：本地 Chrome 远程调试会话，注入后台管理员 token 与 H5 用户 token 后逐页打开。
- 后台 5 个入口均匹配 `.ai-workbench-page` 主容器，路由 hash 与预期一致。
- H5 商品详情、支付页、评价页均可打开，展示演示支付、真实评价进入智能体治理等提示。
- 内置浏览器控制连接受本机 Node 24 ESM/CJS 启动兼容问题影响，改用本地 Chrome 完成真实页面渲染检查。
