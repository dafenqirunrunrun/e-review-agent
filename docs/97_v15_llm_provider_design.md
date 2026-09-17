# v1.5 LLM Provider 设计

## 1. 目标与边界

v1.5 在既有评论治理闭环前增加可选 LLM Provider 层，用于生成风险解释和运营建议。系统仍以人工复核为最终决策，不接真实支付、短信、实名、OSS 或链服务，也不宣称达到生产级 SaaS 能力。

本阶段支持三种 Provider：

- `qwen_openai_compatible`：通过通义千问 OpenAI-compatible API 调用；
- `deepseek_openai_compatible`：通过 DeepSeek OpenAI-compatible API 调用；
- `local_rule_fallback`：复用现有本地规则分析器，无网络、无 API Key 也可运行。

Qwen 与 DeepSeek 均是可选接入。当前演示环境没有写入或提交任何真实 API Key，因此自动使用本地 fallback；评估报告不把本地规则结果描述为远程模型效果。

## 2. 配置

Provider 配置由 `ai-service/app/llm/config.py` 读取，包含：`provider_name`、`base_url`、`model_name`、`api_key_env`、`timeout_seconds`、`max_retries`、`enabled`、`fallback_provider`。

环境变量：

```text
E_REVIEW_LLM_PROVIDER=qwen
E_REVIEW_QWEN_BASE_URL=<QWEN_OPENAI_COMPATIBLE_BASE_URL>
E_REVIEW_QWEN_MODEL=qwen-plus
E_REVIEW_QWEN_API_KEY=
E_REVIEW_DEEPSEEK_BASE_URL=<DEEPSEEK_OPENAI_COMPATIBLE_BASE_URL>
E_REVIEW_DEEPSEEK_MODEL=deepseek-chat
E_REVIEW_DEEPSEEK_API_KEY=
E_REVIEW_LLM_TIMEOUT_SECONDS=30
E_REVIEW_LLM_MAX_RETRIES=2
```

API Key 只从对应环境变量读取。状态接口只返回环境变量名称和是否可用，不返回密钥值；数据库、日志、文档和 Trace 均不保存授权头。

## 3. 调用与回退流程

1. `/api/v1/llm/review/analyze` 先运行原规则工作流，形成稳定的基础响应和 fallback 候选；
2. 若远程 Provider 配置完整，则调用 `/chat/completions`，要求 JSON object；
3. 使用 Pydantic Schema 校验模型内容；
4. 首次输出非法时，以 `json_repair_zh.md` 发起一次修复调用；
5. 修复仍失败、超时、HTTP 错误或响应缺字段时，返回 `local_rule_fallback`；
6. 若未配置 API Key，直接进入本地 fallback，不发起外网请求。

网络调用按 `max_retries` 重试。异常信息会归一化为错误类型，不包含 API Key、授权头或远程完整响应。

## 4. 接口

- `POST /api/v1/llm/review/analyze`：返回兼容旧分析结构并附带 LLM 元数据；
- `GET /api/v1/llm/provider/status`：返回当前选择、可用性和 fallback 状态；
- `POST /api/v1/llm/schema/validate`：校验传入 `data`；
- `POST /api/v1/llm/schema/repair`：执行保守的结构修复，不补造业务事实；
- `POST /api/v1/review/analyze`：原接口保留，并接入同一 Provider 编排器。

## 5. 可观测与落库

迁移文件 `litemall-db/sql/litemall_ai_llm_observability_v15.sql` 为 Agent Run、Agent Step 增加 Provider、模型、Prompt、Schema、repair、fallback、Token 和延迟字段；工具调用日志增加 Provider、请求摘要、响应摘要、状态、错误和延迟。

摘要最多保存 512 字符，不记录完整敏感请求头。迁移可在 MySQL 5.7/8.x 重复执行。现有 Agent Run、Step、Tool Registry、风险任务和运营处理流程保持不变。

## 6. 当前限制

- 当前真实 Qwen/DeepSeek 效果未在无 Key 环境中评估；
- Token 用量依赖远程 Provider 返回 `usage`，本地 fallback 为 0；
- Prompt 注入、内容安全和供应商限流只做基础防护，仍需人工复核；
- LLM 建议不自动执行退款、封禁、赔付或其他最终业务动作。
