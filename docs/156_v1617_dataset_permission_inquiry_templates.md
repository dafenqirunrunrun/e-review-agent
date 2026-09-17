# v1.6.1.7 Dataset Permission Inquiry Templates

These templates are for manual outreach only. Codex must not send messages or
interpret non-responses as approval.

## English Template

Subject: Permission clarification for academic evaluation of ecommerce review AI system

Dear dataset maintainers,

I am working on an academic graduation project named E-Review Agent, an AI Agent
system for ecommerce review governance. I would like to ask whether your dataset
may be used under the following limited conditions.

Could you please clarify:

1. Is academic research use permitted?
2. May we locally download and store review or dialogue text?
3. May we locally download and store review, product, or dialogue images?
4. May we use images for local VLM inference evaluation?
5. May we use the data to train or fine-tune models?
6. May we publish derived aggregate statistics and model metrics?
7. May we publish a small number of anonymized examples in a thesis or slides?
8. May we publish data processing scripts without redistributing raw data?
9. What attribution or citation is required?
10. Are there deletion, retention, privacy, or redistribution restrictions?

We will not redistribute raw text, raw images, user identifiers, signed URLs, or
personal information unless explicitly permitted. Raw pilot data will be stored
outside Git and privacy-filtered before analysis.

Thank you for your help.

## Chinese Template

主题：关于电商评论治理 AI 系统学术评测使用数据集的授权确认

老师/维护者您好：

我正在完成一个毕业设计项目 E-Review Agent，研究方向是电商评论治理中的
AI Agent、文本分析和多模态视觉证据评估。计划只做小规模学术评测和流程验证，
在使用前希望确认贵数据集的许可边界。

烦请确认以下问题：

1. 是否允许学术研究使用？
2. 是否允许本地下载和保存评论或对话文本？
3. 是否允许本地下载和保存评论图片、商品图片或对话图片？
4. 是否允许使用图片进行本地 VLM 推理评测？
5. 是否允许使用数据训练或微调模型？
6. 是否允许发布派生的统计结果和模型指标？
7. 是否允许在论文或答辩材料中展示少量脱敏样例？
8. 是否允许公开数据处理脚本，但不公开原始数据？
9. 是否有署名、引用或致谢要求？
10. 是否有删除期限、保留期限、隐私处理或再分发限制？

如果未获得明确许可，我们不会再分发原始文本、原始图片、用户标识、带签名
参数的 URL 或个人信息。试点原始数据会保存在 Git 仓库之外，并在分析前做隐私
审计和脱敏。

感谢您的帮助。

## Internal Note

Save replies as project evidence only after removing email addresses, personal
names, tokens, signed URLs, and any private contact details that should not enter
Git.
