# 工具协议清单设计

## 目标

工具协议清单用于把 E-Review Agent 的本地工具能力从“页面展示”提升为“可导出、可校验、可追踪”的协议描述。它服务于毕业设计展示中的平台化说明，不代表系统已经接入外部 MCP 服务。

## 协议格式

| 格式 | 说明 | 接口 |
| --- | --- | --- |
| 工具协议清单 | 系统内部统一工具描述，包含名称、说明、输入输出结构、风险等级、审批要求和启用状态。 | `GET /admin/ai/tool/manifest/local` |
| OpenAPI 风格描述 | 将每个工具表达为 operationId、description、parameters 和 responses，便于说明接口契约思想。 | `GET /admin/ai/tool/manifest/openapi` |
| 本地 MCP 风格描述 | 使用类似工具定义的 JSON 结构表达本地工具，但明确不是外部 MCP 服务接入。 | `GET /admin/ai/tool/manifest/mcp-like` |
| JSON 下载 | 按格式导出 JSON 文件。 | `GET /admin/ai/tool/manifest/download?format=local` |

## 字段设计

- 工具名称：稳定的工具标识。
- 展示名称：面向后台页面和答辩讲解。
- 输入输出结构：JSON Schema 风格的本地结构描述。
- 风险等级：低风险、中风险、高风险或严重风险。
- 审批要求：高风险状态变更类工具需要人工确认。
- 启用状态：用于演示工具治理能力。

## Trace 对齐

智能体执行步骤中的工具名称会与工具注册中心进行对齐。未登记工具会进入未注册工具统计，便于后续补充协议定义。

## 边界声明

本设计只提供本地协议描述和导出能力，不声明生产级工具协议，不连接外部 MCP 服务，不连接外部向量数据库。
