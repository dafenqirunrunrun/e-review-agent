# E-Review Agent v2.4 数据集协议研究包

版本：`research-pack-v0.1`
日期：`2026-07-28`
当前状态：`RESEARCH_BASED_DRAFT / REPOSITORY_AUDIT_REQUIRED`

## 1. 这套文件解决什么问题

本包先固化“收什么、从哪里收、如何筛、如何去重、怎么标、如何防泄漏、怎样审核”的统一规则，避免后续收集过程中出现：

- 风险标签在 Java、Python、数据库和文档中各写一套；
- 同一评论在开发集和 Held-out 中以改写形式重复；
- LLM 生成候选后自己给自己标 Gold；
- 没有 Gold Evidence，导致只能测分类、无法测检索与 Citation；
- 用测试样本改 Prompt、知识库或阈值后，仍将其当作严格 Held-out；
- 删除模型答错样本或临时修改标签；
- 原始文本、脱敏文本、规范化文本相互覆盖；
- 指标不错，但无法解释数据来源、标注过程和适用边界。

## 2. 应放到哪里

推荐先创建独立 Worktree：

```powershell
cd D:\EReviewAgent\litemall

git worktree add `
  -b design/v24-dataset-protocol-v01 `
  D:\EReviewAgent\litemall-v24-dataset-protocol `
  d8a3ebbc
```

然后把压缩包中的 `docs` 文件夹解压到：

```text
D:\EReviewAgent\litemall-v24-dataset-protocol\
```

最终目录应为：

```text
D:\EReviewAgent\litemall-v24-dataset-protocol\
└─ docs\
   └─ v24_dataset_protocol\
      ├─ 00_RESEARCH_SYNTHESIS.md
      ├─ 01_DATASET_OBJECTIVES.md
      ├─ ...
      ├─ schema\
      ├─ scripts\
      ├─ examples\
      └─ dataset_protocol_validation.json
```

根目录中的：

```text
CODEX_AUDIT_AND_ADAPT_PROMPT.md
```

建议也复制到 Worktree 根目录，直接交给 Codex 执行。

## 3. 重要状态标签

所有文档使用四类事实标签：

- `CURRENT_PROJECT_FACT`：来自当前会话中已完成的工程验证；
- `RESEARCH_COMMON_PRACTICE`：来自公开论文或Benchmark的共同经验；
- `PROPOSED_PROTOCOL`：针对本项目提出的规则；
- `REPOSITORY_VERIFICATION_REQUIRED`：必须由 Codex 从真实代码、数据库或资产文件核验。

在 Codex 完成仓库核验之前，本包不能宣布为正式 `dataset-protocol-v1.0`。

## 4. 验证命令

使用已经验证的 Python 环境：

```powershell
$PY = "D:\anaconda\envs\ereview-v24-transformers451\python.exe"

& $PY -m pip install "jsonschema>=4.20,<5"

& $PY docs\v24_dataset_protocol\scripts\validate_protocol_schemas.py
& $PY docs\v24_dataset_protocol\scripts\check_protocol_consistency.py
& $PY docs\v24_dataset_protocol\scripts\check_required_terms.py
```

## 5. 当前允许进入的下一阶段

完成 Codex 代码级核验、P0/P1 清零以后，最多只允许进入：

```text
阶段2.1：60条 Pilot 候选收集与双人试标
```

不得直接开始：

```text
500条严格 Held-out
正式模型质量评测
```
