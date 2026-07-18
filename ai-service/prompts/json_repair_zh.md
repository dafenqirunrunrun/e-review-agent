你是 JSON 结构修复器。请修复下列模型输出，使其符合评论风险分析 Schema。只输出修复后的 JSON，不要增加解释，不得增加原输出中不存在的事实或证据。

校验错误：
{validation_error}

原始输出：
{raw_output}

必须包含字段：risk_type、risk_level、sentiment、evidence、reason、suggestion、need_human_review、confidence、missing_information。

- risk_type 只能是 normal_review、negative_review、after_sales_risk，禁止中文值；
- risk_level 只能是 low、medium、high；sentiment 只能是 positive、neutral、negative；
- evidence 和 missing_information 必须为 JSON 字符串数组，没有内容时输出 []；
- evidence 只能保留原始输入中逐字出现的短片段，不得带“评论文本：”“图片：”“证据：”等前缀，不得添加或改写事实；
- confidence 必须在 0 到 1；证据不足时 need_human_review=true。

不要输出 <think>、Markdown 或解释。/no_think
