# v2 Qualification Asset Contract

## Purpose

v2 qualification may require private runtime assets that are too large or too machine-specific to commit: BGE-M3 model files, FAISS `index.faiss`, reranker weights and local LLM weights. These assets must be configured explicitly so default tests stay reproducible on a clean checkout.

## Environment Variable

Set `AGENT_RAG_QUALIFICATION_ASSET_MANIFEST` to an external JSON file, for example:

```text
D:\EReviewAgent\qualification\local-assets\v2.1-assets.json
```

Do not commit the real manifest when it contains local absolute paths or private model locations.

## Repository Files

- Schema: `schemas/qualification/qualification-asset-manifest.schema.json`
- Example: `docs/qualification/examples/v2.1-assets.example.json`
- Verifier: `ai-service/scripts/qualification/verify_qualification_asset_manifest.py`

## Expected Verifier Tokens

When assets are configured and valid:

```text
QUALIFICATION_BGE_ASSET_PASS
QUALIFICATION_DENSE_INDEX_ASSET_PASS
```

When assets are absent:

```text
QUALIFICATION_BGE_ASSET_BLOCKED
QUALIFICATION_DENSE_INDEX_ASSET_BLOCKED
QUALIFICATION_RERANKER_ASSET_BLOCKED
QUALIFICATION_LLM_ASSET_BLOCKED
```

Absent assets are a qualification blocker, not a default code regression failure.

## Boundary

The repository must not include:

- `index.faiss`
- model weights
- wheelhouse directories
- private absolute asset manifests
- local database backups
- runtime logs or PID files
