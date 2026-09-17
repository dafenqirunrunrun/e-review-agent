# 工具注册与权限设计

## 目标

工具注册中心用于把智能体可调用能力显式化，让答辩老师可以看到“系统调用了哪些工具、工具风险等级是什么、是否需要人工审批、调用是否成功”。该设计借鉴函数工具、动作结构和 MCP 元数据思想，但当前实现完全在本地运行。

## 本地工具清单

默认展示的工具包括：

- `review_text_analyzer`：评论文本分析。
- `image_url_signal_extractor`：图片链接信号提取。
- `risk_rule_checker`：风险规则检查。
- `case_retriever`：相似案例检索。
- `operation_suggestion_generator`：运营建议生成。
- `risk_task_creator`：风险任务创建。
- `feedback_writer`：人工反馈写入。
- `demo_product_seed_checker`：演示商品检查。
- `health_checker`：服务健康检查。

每个工具展示字段包括工具名称、展示名称、描述、分类、输入输出结构、风险等级、是否需要审批、启用状态、调用次数和近期失败次数。

## 权限模型

低风险工具可直接执行；中风险工具保留告警和审计；高风险工具需要记录审批状态。当前审批流程是本地实验能力：

1. 系统读取工具策略。
2. 高风险工具被标记为需要审批。
3. 管理员可在工具注册中心批准或拒绝。
4. 执行追踪和工具日志展示审批结果。

## 接口范围

接口路径保持英文和原有命名，以保证前后端契约稳定：

- `GET /admin/ai/tool/registry/list`
- `GET /admin/ai/tool/registry/detail`
- `POST /admin/ai/tool/registry/update-enabled`
- `GET /admin/ai/tool/policy/list`
- `POST /admin/ai/tool/policy/update`
- `GET /admin/ai/tool/execution/logs`
- `POST /admin/ai/tool/approval/approve`
- `POST /admin/ai/tool/approval/reject`
- `GET /admin/ai/tool/approval/pending`

## 存储说明

表结构记录在 `litemall-db/sql/litemall_ai_enterprise_agent_platform.sql`。即使未执行迁移，前端也可基于本地服务级定义和已有智能体步骤数据展示核心内容，不会破坏 v1.0.4 主流程。
## v1.2 补充

v1.2 在工具注册中心上增加工具协议清单、OpenAPI 风格描述和本地 MCP 风格描述导出，并增加结构校验、契约测试、未注册工具检查和审批时间线。该能力只描述本地工具协议，不代表接入外部 MCP 服务。
