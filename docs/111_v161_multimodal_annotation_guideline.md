# v1.6.1 图文评论标注规范

## 目标

本规范用于真实图文评论的视觉证据、图文一致性和隐私风险标注。Qwen3-VL 只负责视觉证据提取；Qwen3-1.7B 才负责综合治理判断。

## 视觉字段

| 字段 | 取值或说明 |
| --- | --- |
| `image_quality` | `clear`、`blurred`、`occluded`、`irrelevant`、`uncertain` |
| `ocr_text` | 图片可见文字；若含隐私只保留脱敏摘要 |
| `package_damage` | 包装破损、挤压、变形等 |
| `product_damage` | 商品本体破损、裂开、碎裂等 |
| `leakage` | 漏液、污染、渗出痕迹 |
| `missing_part` | 可见缺件或清单无法对应 |
| `product_mismatch` | 图片实物与文本/商品描述明显不一致 |
| `irrelevant_image` | 与商品或评价无关 |
| `privacy_risk` | 人脸、手机号、地址、订单号、快递单等 |
| `visual_evidence` | 仅来自图片可见内容的证据 |
| `text_image_consistency` | `consistent`、`conflicting`、`unrelated`、`uncertain` |
| `visual_uncertainty` | 看不清、遮挡、证据不足时为 true |

## 标注边界

1. 文本证据与视觉证据必须分开标注。
2. 不允许根据评论文本反向标注图片内容。
3. 看不清时标记 `uncertain`，不得猜测。
4. 不允许根据图片推测品牌真伪，除非存在清晰可核验的防伪或包装证据。
5. 包装轻微变形不能直接标记商品本体损坏。
6. VLM 输出不能直接决定退款、赔付、封禁或商家处罚。
7. 发现隐私风险时，不保存完整 OCR 文本和原始图片到 Git。

## 双人标注与一致性

- 至少 40 组图文样本需要双人标注。
- 对 `image_quality`、主要视觉风险标签、`text_image_consistency` 计算一致性。
- 无第二标注人时必须报告限制，不得伪造 Kappa 或 Alpha。

## 图片存储

1. 原始图片必须位于仓库外，例如 `data-private/multimodal-images`。
2. Git 中只保存 `image_ids`、不可逆 hash、许可证、隐私状态和脱敏派生信号。
3. external test 图片不得用于 Prompt 调试、模型选择、阈值校准或任何 VLM 微调。
