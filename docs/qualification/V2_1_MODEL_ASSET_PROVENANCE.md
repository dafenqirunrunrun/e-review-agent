# v2.1 Model Asset Provenance Contract

## External Asset Directory

All real model and scan assets must stay outside Git:

```text
D:\EReviewAgent\qualification\v2.1-assets
```

Recommended structure:

```text
v2.1-assets/
  models/reranker/
  models/llm/
  manifests/qualification-assets.json
  vulnerability/outbound/
  vulnerability/inbound/
  evidence/
  logs/
```

## Required Model Evidence

Each real model asset must provide:

- model name
- source and revision
- download time and machine
- file count and total size
- asset fingerprint
- architecture
- config files
- weight format
- license ID
- license evidence
- redistribution restrictions

Repository files only define schema and documentation. Real paths, model
weights, wheelhouses and private manifests must not be committed.

## Current State

No trusted reranker or local LLM model asset is configured in this worktree.

```text
MODEL_RERANKER_NOT_VERIFIED
REAL_LLM_QUALITY_NOT_VERIFIED
```
