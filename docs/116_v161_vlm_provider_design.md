# v1.6.1 VLM Provider 设计

## 目标

VLM Provider 用于提取当前评论图片中的结构化视觉证据，不替代 Qwen3-1.7B 的最终治理判断。当前实现已经接入状态、Schema 校验、图文一致性辅助和 smoke-test 阻塞路径；由于本机尚未提供 `Qwen3-VL-2B-Instruct` 或 `Qwen2.5-VL-3B-Instruct` 权重，本阶段不能声明真实 VLM 推理完成。

## Provider

- provider：`local_qwen3_vl_transformers`
- 优先模型：`Qwen3-VL-2B-Instruct`
- 默认模型目录：仓库外 `models/Qwen3-VL-2B-Instruct`
- 权重位置：Git 仓库外
- 默认显存策略：`serial_lazy_load`
- 默认 4-bit：`true`
- 默认最多图片：4
- 默认最大像素：1048576

## API

| 接口 | 当前行为 |
| --- | --- |
| `GET /api/v1/vlm/status` | 返回 provider、模型目录、模型是否可用、显存策略 |
| `POST /api/v1/vlm/schema/validate` | 校验视觉 JSON Schema |
| `POST /api/v1/vlm/text-image/consistency` | 基于视觉结果给出一致性与是否转人工 |
| `POST /api/v1/vlm/smoke-test` | 模型缺失时返回 `MULTIMODAL_VLM_EVAL_BLOCKED` |
| `POST /api/v1/vlm/image/analyze` | 模型缺失时 HTTP 503，禁止用人工标签假装 VLM 输出 |

## 当前 smoke 状态

本机模型目录检查结果：

- 仓库外 `models/Qwen3-VL-2B-Instruct`：不存在
- 仓库外 `models/Qwen2.5-VL-3B-Instruct`：不存在

因此当前状态为：`MULTIMODAL_VLM_EVAL_BLOCKED`。

## 显存策略

本机 RTX 4060 Laptop 8GB 不允许 Qwen3-1.7B、Qwen3-VL、BGE-M3 和 Neural Reranker 同时长期驻留显存。当前设计采用串行惰性加载：

1. 图片分析阶段加载 VLM；
2. 完成图片分析后卸载 VLM；
3. 执行 `gc.collect()`；
4. 执行 `torch.cuda.empty_cache()`；
5. 再执行文本 Qwen3-1.7B 治理决策。

OOM 时必须转人工，不能静默丢弃图片。

## 后续真实 smoke 条件

只有满足以下条件才能把 BLOCKED 改为 PASS：

1. 模型权重位于仓库外；
2. `GET /vlm/status` 显示 `model_available=true`；
3. 使用至少一张合规、无隐私的测试图片执行真实 `image/analyze`；
4. 输出通过视觉 Schema；
5. 记录平均延迟、P95 延迟和 GPU 峰值显存；
6. 不提交原始图片和模型权重。
