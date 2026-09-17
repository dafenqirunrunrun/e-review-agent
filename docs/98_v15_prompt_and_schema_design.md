# v1.5 Prompt 与 JSON Schema 设计

## 1. Schema

结构化输出模型位于 `ai-service/app/llm/schemas.py`：

```json
{
  "risk_type": "string",
  "risk_level": "low | medium | high",
  "sentiment": "positive | neutral | negative",
  "evidence": ["string"],
  "reason": "string",
  "suggestion": "string",
  "need_human_review": true,
  "confidence": 0.0,
  "missing_information": ["string"]
}
```

Pydantic 执行以下约束：风险等级和情感为枚举；`need_human_review` 为布尔值；置信度在 0 到 1；`evidence` 与 `missing_information` 必须是数组且不能为 null；风险类型、理由和建议不能为空字符串。

JSON Schema 的目的不是证明模型判断正确，而是控制字段完整性、类型和取值范围，使结果可校验、可落库、可评估。

## 2. Prompt 模板

模板目录为 `ai-service/prompts/`：

- `review_risk_analysis_zh.md`：评论风险结构化分析；
- `operation_suggestion_zh.md`：运营建议边界；
- `json_repair_zh.md`：非法 JSON 修复。

模板统一要求中文内容、只输出 JSON、禁止编造证据。`evidence` 只能来自评论文本、图片信号或明确提供的检索案例；证据不足、图文冲突或置信度不足时，必须设置 `need_human_review=true` 并填写缺失信息。

## 3. 校验、repair 与 fallback

Provider 原始字符串先移除可选 Markdown 代码围栏，再提取第一个完整 JSON 对象。解析或 Schema 校验失败时触发模型 repair；repair Prompt 只允许修复结构，不允许增加原输出不存在的事实或证据。

独立 `/schema/repair` 接口采用保守的确定性修复：非法枚举回到 `medium/neutral`，非法置信度截断到 0 至 1，缺字段使用“证据不足、人工复核”语义。模型 repair 再次失败后不继续猜测，直接使用已有 `local_rule_fallback`。

## 4. 与旧响应兼容

Provider 输出映射到原 `ReviewAnalyzeResponse`：

- `sentiment` 映射为 `sentiment_label`；
- `suggestion` 映射为 `agent_suggestion.operation_advice`；
- `reason` 写入建议摘要与 `extra.llm_reason`；
- `risk_type` 写入 `extra.risk_type`；
- 原 `scores`、图像分、冲突分、相似案例和工作流 Trace 继续保留。

新增元数据包括 `llm_provider`、`model_name`、`prompt_template`、`schema_valid`、`schema_error`、`repair_used`、`fallback_used`、Token 用量、延迟、`need_human_review` 和 `missing_information`。

## 5. 评估设计

`data/eval/review_schema_eval.jsonl` 含 100 条小型测试数据，覆盖正向、中性、负向、售后风险和混合证据信号。每条包括评论、图片信号、期望风险类型、期望人工复核和证据关键词。

`scripts/e-review-llm-schema-eval.ps1` 调用实际运行的 FastAPI HTTP 接口，Python 评估器统计 Schema 有效率、字段完整率、风险类型/等级准确率、证据支持率、无依据声明率、fallback 率和平均延迟。只有满足三个规定门槛时才输出 `LLM_SCHEMA_EVAL_PASS`。

评估结论见 `docs/96_v15_llm_json_schema_eval_report.md`。该报告只代表当前数据集和当前 Provider 配置，不将本地规则指标冒充 Qwen/DeepSeek 模型指标。
