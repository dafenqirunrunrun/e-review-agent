# V2 Reranker Model Audit

## Model Asset Policy

Reranker model weights are not stored in this repository. Operators may configure
a local model path through `RAG_RERANKER_MODEL_PATH`.

## Required Asset Checks

- `config.json`
- tokenizer metadata such as `tokenizer.json` or `tokenizer_config.json`
- model weights such as `.safetensors`, `.bin`, or `.pt`
- optional weight index files

## Sanitized Evidence

The runtime records only a path hint, model name, and stable asset fingerprint.
It does not persist absolute local paths.

## Current Verification Boundary

When no local model path is configured or the asset is incomplete, the gate emits:

```text
AGENT_RAG_MODEL_RERANKER_BLOCKED
AGENT_RAG_PHASE3B_BLOCKED
```

This means deterministic fallback is working, but real model reranking has not
been verified.
