# 12 版本与Manifest

## 1. 版本链

```text
dataset-protocol-v0.1
→ pilot-60-v0.1
→ dataset-protocol-v1.0
→ raw-candidates-v0
→ screened-candidates-v1
→ deduplicated-candidates-v1
→ heldout-500-v1
→ heldout-500-v1.sealed
```

## 2. 版本规则

### Patch

不改变标签语义、样本或Split的文档纠错。

### Minor

新增非破坏字段、说明或质量检查，但旧数据仍兼容。

### Major

任一情况必须升Major：

- 风险类别语义变化；
- 严重程度边界变化；
- Gold Evidence粒度变化；
- 样本内容变化；
- Gold标签变化；
- Split变化；
- 去重规则导致最终集合变化；
- 评测指标定义变化。

## 3. Manifest

正式Dataset Manifest必须记录：

- datasetVersion；
- protocolVersion；
- schemaVersion；
- sampleCount；
- sourceDistribution；
- riskDistribution；
- severityDistribution；
- answerabilityDistribution；
- syntheticRatio；
- datasetHash；
- sourceManifestHash；
- dedupReportHash；
- annotationGuidelineHash；
- adjudicationLogHash；
- createdAt；
- sealedAt；
- codeCommit；
- indexManifest；
- modelAssetManifest。

## 4. 当前状态

本研究包只能标记：

```text
PROTOCOL_ONLY
DATASET_NOT_COLLECTED
DATASET_NOT_FROZEN
REPOSITORY_AUDIT_REQUIRED
```

## 5. 不可变原则

封存后不得原地修改：

- 样本；
- Gold；
- Split；
- Evidence；
- Manifest。

修改必须产生新版本和新Hash。
