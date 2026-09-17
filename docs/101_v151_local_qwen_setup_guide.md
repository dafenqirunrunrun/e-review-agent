# v1.5.1 本地 Qwen3 运行指南

## 1. 前置条件

- Python 环境包含 PyTorch、Transformers 4.51 或更高版本、FastAPI、Pydantic 和 HTTPX；
- 建议使用支持半精度推理的 NVIDIA GPU；
- 模型权重位于 Git 仓库之外；
- 不需要 Hugging Face Token 即可下载公开模型，禁止把 Token 写入项目。

本机验证使用：

- Python：现有 Conda `torchtest` 环境；
- GPU：RTX 4060 Laptop 8GB；
- 模型目录：`<PROJECT_ROOT_PARENT>\models\Qwen3-1.7B`；
- 模型来源：Qwen 官方 `Qwen/Qwen3-1.7B`，Apache-2.0；
- thinking：关闭。

## 2. 环境变量

```powershell
$env:E_REVIEW_LLM_PROVIDER = "local_qwen3_transformers"
$env:E_REVIEW_LOCAL_QWEN_MODEL = "Qwen/Qwen3-1.7B"
$env:E_REVIEW_LOCAL_QWEN_MODEL_DIR = "<PROJECT_ROOT_PARENT>\models\Qwen3-1.7B"
$env:E_REVIEW_LOCAL_QWEN_DEVICE = "auto"
$env:E_REVIEW_LOCAL_QWEN_TORCH_DTYPE = "auto"
$env:E_REVIEW_LOCAL_QWEN_MAX_NEW_TOKENS = "512"
$env:E_REVIEW_LOCAL_QWEN_ENABLE_THINKING = "false"
$env:E_REVIEW_LOCAL_QWEN_TIMEOUT_SECONDS = "120"
```

不要在 `.env.example` 中填写 Token，也不要提交本地 `.env`。

## 3. 启动与冒烟测试

使用包含 PyTorch 的 Python 环境启动 AI 服务：

```powershell
cd <PROJECT_ROOT>\ai-service
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/v1/llm/provider/status
```

状态应显示 `provider_name=local_qwen3_transformers`、`local_model_loaded=true`、`enable_thinking=false`。首次推理包含模型加载时间。

## 4. 100 条评估

```powershell
$env:E_REVIEW_LOCAL_QWEN_PYTHON = "<PYTHON_WITH_TORCH>"
$env:E_REVIEW_LOCAL_QWEN_MODEL_DIR = "<PROJECT_ROOT_PARENT>\models\Qwen3-1.7B"
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-local-qwen-schema-eval.ps1
```

脚本会在 8010 启动临时服务、运行 100 条测试、生成报告并停止临时服务。只有真实 Qwen3 成功率达到 80% 且 Schema、字段完整性和无依据声明率达到门槛时，才输出 `LOCAL_QWEN_SCHEMA_EVAL_PASS`。

依赖、模型、显存或下载不可用时，脚本输出 `LOCAL_QWEN_SCHEMA_EVAL_BLOCKED`，不会把 fallback 写成 Qwen3 PASS。

## 5. 常见问题

- `LOCAL_QWEN_DEPENDENCY_NOT_AVAILABLE`：切换到已安装 PyTorch 和新版本 Transformers 的环境；
- `LOCAL_QWEN_MODEL_NOT_AVAILABLE`：检查模型目录内是否有 config、tokenizer、索引和全部权重分片；
- `LOCAL_QWEN_CUDA_OOM`：关闭占用 GPU 的进程，或改为 CPU 验证；
- 输出包含 thinking：确认环境变量为 false，并检查 Prompt 末尾 `/no_think`；
- Schema 失败：查看 repair 与 fallback 字段，不要手工修改评估结果。

## 6. 简历表述边界

只有报告为 `LOCAL_QWEN_SCHEMA_EVAL_PASS` 时，才可以写“接入 Qwen3-1.7B 本地开源模型并完成结构化风险分析测试”。若报告为 BLOCKED，只能写“实现本地 Qwen3 Provider，当前环境未完成模型推理验证”。

## 7. 当前验证结论

当前仓库对应版本已在本机真实完成模型下载、CUDA 加载、烟测和 100 条评估，最终报告为 `LOCAL_QWEN_SCHEMA_EVAL_PASS`。本次使用 Transformers 5.3.0、PyTorch 2.5.1+cu121 和 RTX 4060 Laptop 8GB；没有使用 OpenAI-compatible endpoint，也没有使用规则 fallback 代替 Qwen 指标。

最终关键指标为：Schema 有效率 100%、字段完整率 100%、本地 Qwen 成功率 100%、fallback 率 0%、风险类型/等级准确率 84%、证据支持率 100%、无依据声明率 0%、平均延迟 2825.88 ms、P95 延迟 3217.00 ms。模型权重仍只保存在 Git 仓库外。
