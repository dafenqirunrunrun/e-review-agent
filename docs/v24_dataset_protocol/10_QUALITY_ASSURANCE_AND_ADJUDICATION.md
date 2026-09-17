# 10 质量保证、复标与仲裁

## 1. Pilot 60

- 60条全部双人独立标注；
- 所有主要类别与边界都要覆盖；
- 所有分歧必须仲裁；
- Pilot只用于修订协议；
- Pilot不得作为最终Held-out指标。

## 2. 正式500条

建议：

- 主标注者完成500条；
- 至少100条第二人独立复标；
- 以下样本100%双标：
  - 高风险；
  - 安全风险；
  - 多风险；
  - 无答案；
  - 证据不足；
  - 歧义；
  - requiresAdjudication=true。

## 3. 一致性指标

- 主风险类型：Cohen's Kappa；
- 风险等级：Weighted Kappa；
- 是否人工复核：Cohen's Kappa；
- Gold Evidence：Passage-level Precision/Recall/F1；
- 多标签：Jaccard或Example-based F1。

Pilot门禁候选值：

- κ ≥ 0.75：可以进入正式协议冻结；
- 0.60 ≤ κ < 0.75：修订指南后重新试标；
- κ < 0.60：禁止进入正式收集。

## 4. 仲裁记录

每个分歧必须保存：

- sampleId；
- annotatorA/B；
- 分歧字段；
- 各自理由；
- adjudicatorId；
- finalDecision；
- appliedRule；
- guidelineChangeRequired；
- previousGuidelineVersion；
- finalGuidelineVersion。

## 5. 问题分级

- P0：隐私、泄漏、Gold错误、数据不可用；
- P1：标签边界、去重、Split、指标不一致；
- P2：自动化或维护问题；
- P3：表达与优化建议。

进入Pilot条件：

- P0=0；
- P1=0；
- Schema通过；
- 文档一致；
- 仓库字段核验完成。

## 6. LLM辅助边界

LLM可以：

- 预标候选；
- 提示缺失字段；
- 推荐可能证据；
- 发现潜在重复。

LLM不能独立批准：

- 最终Gold风险类型；
- 最终严重程度；
- 最终Gold Evidence；
- 是否封存；
- 分歧仲裁。
