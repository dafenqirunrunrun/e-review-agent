# v1.5.1 本地 Qwen3 Provider 设计

## 1. 目标与模型选择

v1.5.1 在既有 Qwen/DeepSeek OpenAI-compatible Provider 和本地规则 fallback 之外，增加 `local_qwen3_transformers` 与可选的 `local_qwen3_openai_compatible`。默认模型为 `Qwen/Qwen3-1.7B`。

选择该模型的原因是参数规模为 1.7B、Apache-2.0 许可证、支持 Transformers 推理，并可作为后续 ms-swift、QLoRA-SFT 和 DPO 实验的开源基座。本阶段只做推理与结构化输出评估，不做训练或微调。

## 2. Transformers 实现

实现文件为 `ai-service/app/llm/local_qwen.py`。`LocalQwenTransformersProvider` 使用 `AutoTokenizer` 和 `AutoModelForCausalLM`，模型在第一次请求时懒加载，因此没有安装 PyTorch或没有模型权重时不会阻止 FastAPI 启动。

加载优先级：

1. 配置 `E_REVIEW_LOCAL_QWEN_MODEL_DIR` 时只读取该本地目录，不隐式联网；
2. 未配置目录时使用 `E_REVIEW_LOCAL_QWEN_MODEL`，由 Transformers 按其缓存与下载策略处理；
3. `device=auto` 时优先 CUDA，否则使用 CPU；
4. 安装 Accelerate 时支持 `device_map=auto`，未安装时将完整模型移动到自动选择的设备；
5. 模型和 tokenizer 在进程内缓存，后续请求不重复加载。

本机验证环境使用已有 Conda `torchtest` 环境，PyTorch 2.5.1 CUDA 12.1、Transformers 5.3.0、RTX 4060 Laptop 8GB。没有为本阶段自动安装大型依赖。

## 3. 非思考与 JSON 策略

默认 `E_REVIEW_LOCAL_QWEN_ENABLE_THINKING=false`。调用 `apply_chat_template` 时显式传入 `enable_thinking=false`；旧模板不支持该参数时，在 Prompt 末尾附加 `/no_think`。

系统提示要求只输出 JSON，不输出 Markdown、解释或 `<think>`。解析前会移除完整或残留的 thinking 前缀，再复用 v1.5 的 JSON 提取、Pydantic Schema 校验、模型 repair 和规则 fallback。

## 4. 失败边界

本地 Provider 将失败归类为：

- `LOCAL_QWEN_DEPENDENCY_NOT_AVAILABLE`：缺少 torch 或 transformers；
- `LOCAL_QWEN_MODEL_NOT_AVAILABLE`：本地目录或模型文件缺失；
- `LOCAL_QWEN_CUDA_OOM`：GPU 显存不足；
- `LOCAL_QWEN_LOAD_FAILED:<ExceptionType>`：其他加载或生成错误。

失败后响应必须使用 `local_rule_fallback` 并设置 `fallback_used=true`。错误摘要不包含完整 Prompt、模型输出、Token、授权头或个人目录。

## 5. 可观测

成功推理时 Agent Run 和 Agent Step 记录 `llm_provider=local_qwen3_transformers`、模型名、Schema 状态、repair、fallback、输入/输出 Token 和延迟。Trace 工具名为 `LocalQwenTransformersTool`，Tool Log 同步记录 Provider 与截断后的请求/响应摘要。

模型权重不会写入数据库。Git 忽略规则覆盖 `models/`、Hugging Face 缓存、Safetensors 和 PyTorch 权重文件。

## 6. OpenAI-compatible 选项

若以后使用 vLLM、SGLang 或兼容服务，可选择 `local_qwen3_openai_compatible`，默认端点为本机 8009。该模式复用现有 OpenAI-compatible 请求层，不要求 API Key，但本阶段真实评估以 Transformers 路径为准。

## 7. 系统边界

Qwen3 结果只用于风险解释和运营建议，不能自动执行退款、赔付、封禁等最终决策。系统仍不接真实支付、短信、实名、OSS 或链服务，也不将当前实现描述为生产级 SaaS。

## 8. 本机真实验证结果

本阶段已真实下载并加载 `Qwen/Qwen3-1.7B`，权重位于仓库外的 `<PROJECT_ROOT_PARENT>\models\Qwen3-1.7B`。验证使用 Transformers 路径，不是 OpenAI-compatible endpoint；thinking 显式关闭。模型在 RTX 4060 Laptop 8GB 上以 CUDA / bfloat16 成功运行，测试期间未出现显存不足。

100 条固定测试集评估输出 `LOCAL_QWEN_SCHEMA_EVAL_PASS`：Schema 有效率、字段完整率、本地 Qwen 成功率和证据支持率均为 100%，fallback 与无依据声明率均为 0%，风险类型和风险等级准确率均为 84%，平均延迟 2825.88 ms，P95 延迟 3217.00 ms。完整结果见 `docs/100_v151_local_qwen_schema_eval_report.md`。

隔离端口联调中，Agent Run `117` 已记录 Provider、模型、Schema、Token 与延迟；对应 Agent Step 的工具名为 `LocalQwenTransformersTool`，Tool Log 同步记录 Provider 和截断摘要。该编号仅是本机验证证据，不是跨环境固定标识。

基于本次真实结果，可以在简历中表述“接入 Qwen3-1.7B 本地开源模型并完成 100 条结构化风险分析测试”，但必须保留测试集、本机环境和非生产级模型质量边界。
