# API 参考

本文档用于答辩和联调说明。接口路径、字段名和枚举值保持英文原样，页面展示层负责中文化。

## FastAPI AI 服务

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health` | AI 服务健康检查。 |
| POST | `/api/v1/review/analyze` | 图文评论分析入口。 |
| GET | `/api/v1/agent-framework/status` | 智能体框架与回退状态。 |
| POST | `/api/v1/agent-framework/analyze` | 智能体风格分析入口。 |

## 管理后台接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/admin/auth/login` | 管理员登录。 |
| GET | `/admin/ai/dashboard/summary` | AI 工作台总览摘要。 |
| POST | `/admin/ai/patrol/run-once` | 立即执行一次智能体巡检。 |
| GET | `/admin/ai/risk/list` | 风险评论任务列表。 |
| GET | `/admin/ai/operation/list` | 运营处理任务列表。 |
| GET | `/admin/ai/agent/run/list` | 智能体运行列表。 |
| GET | `/admin/ai/agent/run/state/{runId}` | 运行状态快照、角色摘要和来源分析。 |
| POST | `/admin/ai/agent/run/replay/{runId}` | 重放历史运行，不覆盖原记录。 |
| GET | `/admin/ai/agent/run/compare` | 对比两次运行的情感、置信度、回退和相似案例。 |
| GET | `/admin/ai/agent/eval/summary` | 智能体评估摘要。 |
| GET | `/admin/ai/agent/quality/summary` | 智能体质量摘要。 |
| GET | `/admin/ai/agent/diagnostics/summary` | 智能体诊断摘要。 |
| GET | `/admin/ai/agent/diagnostics/recent-failures` | 最近失败运行或失败步骤。 |
| GET | `/admin/ai/agent/diagnostics/failure-groups` | 失败分组和修复建议。 |
| GET | `/admin/ai/agent/diagnostics/health` | 本地演示服务健康状态。 |
| GET | `/admin/ai/agent/framework/status` | 管理后台侧框架状态代理。 |
| GET | `/admin/ai/case/list` | 案例知识库列表。 |
| GET | `/admin/ai/case/retrieve` | 轻量相似案例检索。 |
| POST | `/admin/ai/case/rebuild-from-history` | 从历史分析和运营处理记录重建本地案例知识库。 |

## H5 用户端接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/wx/home/index` | H5 用户端首页数据。 |
| GET | `/wx/goods/list` | 商品列表。 |
| GET | `/wx/goods/detail` | 商品详情。 |
| POST | `/wx/order/submit` | 提交用户订单。 |
| POST | `/wx/ai-demo/order/mock-pay` | 答辩演示支付成功，不调用真实支付。 |
| POST | `/wx/ai-demo/order/mock-ship` | 答辩演示发货，不调用真实物流。 |
| POST | `/wx/order/confirm` | 复用原订单流程确认收货。 |
| GET | `/wx/order/goods` | 查询订单商品，用于提交评价。 |
| POST | `/wx/order/comment` | 提交真实商品评价并写入 `litemall_comment`。 |

## 响应结构

项目沿用 litemall 统一响应结构：

```json
{
  "errno": 0,
  "errmsg": "success",
  "data": {}
}
```

## v1.1 实验型智能体平台接口

这些接口属于本地实验增强线，用于答辩展示产品化和平台化能力，不代表生产 SaaS 或外部 MCP 接入。

### 工具注册与审批

- `GET /admin/ai/tool/registry/list`
- `GET /admin/ai/tool/registry/detail?toolName=review_text_analyzer`
- `POST /admin/ai/tool/registry/update-enabled`
- `GET /admin/ai/tool/policy/list`
- `POST /admin/ai/tool/policy/update`
- `GET /admin/ai/tool/execution/logs`
- `GET /admin/ai/tool/approval/pending`
- `POST /admin/ai/tool/approval/approve`
- `POST /admin/ai/tool/approval/reject`

### 记忆、安全护栏、运维、注册和检索质量

- `GET /admin/ai/memory/profile/list`
- `GET /admin/ai/memory/profile/detail`
- `POST /admin/ai/memory/rebuild`
- `GET /admin/ai/guardrail/events`
- `GET /admin/ai/guardrail/summary`
- `POST /admin/ai/guardrail/test`
- `GET /admin/ai/agentops/summary`
- `GET /admin/ai/agentops/trends`
- `GET /admin/ai/agentops/slo`
- `GET /admin/ai/agent/registry/list`
- `GET /admin/ai/agent/registry/detail`
- `GET /admin/ai/rag/quality/summary`
## v1.2 工具协议、检索质量和趋势接口

以下接口属于 v1.2 本地实验增强线，用于展示工具协议化、结构校验、契约测试、检索质量和趋势运维能力。不代表系统已经接入外部 MCP 服务或外部向量数据库。

### 工具协议清单

- `GET /admin/ai/tool/manifest/local`
- `GET /admin/ai/tool/manifest/openapi`
- `GET /admin/ai/tool/manifest/mcp-like`
- `GET /admin/ai/tool/manifest/download?format=local`

### 工具结构校验与契约测试

- `GET /admin/ai/tool/schema/validate`
- `POST /admin/ai/tool/schema/test`
- `GET /admin/ai/tool/schema/report`

### 工具日志与审批状态流

- `GET /admin/ai/tool/execution/logs`
- `GET /admin/ai/tool/execution/unregistered`
- `GET /admin/ai/tool/execution/summary`
- `GET /admin/ai/tool/approval/list`
- `GET /admin/ai/tool/approval/detail`
- `POST /admin/ai/tool/approval/mark-executed`
- `POST /admin/ai/tool/approval/mark-reviewed`
- `GET /admin/ai/tool/approval/timeline`

### 案例检索质量

- `GET /admin/ai/case/retrieve-v2`
- `GET /admin/ai/case/retrieve-compare`
- `GET /admin/ai/case/retrieval/failures`
- `GET /admin/ai/case/retrieval/metrics`

### 智能体运维趋势

- `GET /admin/ai/agentops/trends`
- `GET /admin/ai/agentops/recent-runs`
- `GET /admin/ai/agentops/failure-top`
- `GET /admin/ai/agentops/tool-failure-top`
- `GET /admin/ai/agentops/fallback-distribution`
- `GET /admin/ai/agentops/guardrail-trend`
- `GET /admin/ai/agentops/rag-trend`
- `GET /admin/ai/agentops/quality-trend`
