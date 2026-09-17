# v1.6.1.6 Real-World Data Pipeline

## Storage Boundary

Git-external private data root:

`D:\EReviewAgent\data-private\realworld`

Allowed Git paths:

- `data/real_world/source_manifest`
- `data/real_world/schemas`
- `data/real_world/audit`
- `data/real_world/statistics`
- `data/real_world/split_manifest`
- `data/real_world/annotation_manifest`
- `data/real_world/eval`

## Pipeline

1. Audit source license and redistribution terms.
2. Acquire raw text/images only for approved sources.
3. Normalize records without changing semantics.
4. Redact PII from text and images.
5. Deduplicate exact and near duplicates.
6. Build development, validation, and external-test splits.
7. Collect independent annotations and adjudication.
8. Run No-Oracle RAG, Qwen text, VLM, and multimodal ablation evaluation.
9. Keep external-test data isolated from indexing, training, calibration, and prompt selection.

## Current Status

`REALWORLD_DATA_PIPELINE_READY_FOR_APPROVED_SOURCES`

The pipeline and schemas are present. Execution is blocked until at least one
source passes the license audit and private data is acquired outside Git.
