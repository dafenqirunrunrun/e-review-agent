# v1.6.1 真实数据来源与许可证报告

本报告记录本阶段已核实的公开数据源候选。结论只基于公开页面和数据集卡片，不把网页公开等同于允许再发布，不下载或提交原始真实图片。

## 来源结论

| source_id | 用途判断 | 许可证/条款 | 是否可用于本阶段 |
| --- | --- | --- | --- |
| `banglishrev_hf_2024` | 电商评论文本与图文候选 | `cc-by-nc-sa-4.0` | 可作为研究用途候选；必须脱敏、过滤隐私、原始图片留在仓库外 |
| `amazon_reviews_2023_mccauley` | 大规模电商文本候选 | 未在项目页或 HF 卡片找到明确 license | 暂不使用，标记为 license unclear |
| `amazon_berkeley_objects_abo` | 产品图像参考 | `cc-by-4.0` | 可作产品视觉 smoke 参考，但不是评论图片，不能满足图文评论外部测试 |
| `yelp_open_dataset` | 商家评论/图片 | 教育用途条款，不是开放再分发许可证 | 不作为电商商品评论验证集 |

## 依据

- BanglishRev 的 Hugging Face 数据集卡片显示 license 为 `cc-by-nc-sa-4.0`，并标注 Image modality；论文说明数据包含电商评论、评分、商品信息以及评论关联图片。
- Amazon Reviews 2023 项目页说明包含用户评论、item metadata 和 raw image 字段，但本次未找到明确 license，因此不能进入真实外部验证。
- Amazon Berkeley Objects 项目页明确为 CC BY 4.0，包含产品 metadata、catalog images 和 3D models；但它不是用户图文评论数据。
- Yelp Open Dataset 页面说明 intended for educational use，包含 reviews/photos，但对象是 local businesses，不是电商商品评论。

## 当前状态

- 真实评论文本数据：`PUBLIC_REAL_DATA_CANDIDATE_FOUND`，候选为 BanglishRev；尚未下载、抽样、脱敏或划分 dev/external test。
- 真实图文评论数据：`PUBLIC_MULTIMODAL_DATA_CANDIDATE_FOUND`，候选为 BanglishRev；尚未下载图片，原始图片不得进入 Git。
- Amazon Reviews 2023：`PUBLIC_REAL_DATA_LICENSE_BLOCKED`。
- ABO：`PUBLIC_PRODUCT_IMAGE_DATA_AVAILABLE_BUT_NOT_REVIEW_IMAGE`。

## 后续准入要求

1. 下载必须使用官方 Hugging Face 数据集入口或用户手动提供的本地副本。
2. 原始真实图片只能存放在仓库外的 `data-private/multimodal-images` 类目录。
3. Git 中只允许提交 source manifest、不可逆 hash、脱敏文本、派生视觉信号和标注状态。
4. 任何 buyer id、product id、用户名、图片 URL、手机号、地址、订单号、快递单 OCR 均不得入库提交。
5. 外部测试集不得进入索引、Prompt 选择、融合权重选择或阈值校准。

## BanglishRev 本地导入状态

`PUBLIC_REAL_DATA_LOCAL_SOURCE_BLOCKED`：尚未在仓库外提供官方 `reviews v1.json`。建议手动下载到 `data-private/banglishrev/` 后运行导入脚本；本轮不自动下载 2GB 原始文件。
