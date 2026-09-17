# V2 Reranker Decision

## Decision

Keep deterministic reranking as the default and support an optional governed
local model reranker.

## Rationale

This preserves demo stability while allowing enterprise-style upgrade paths.
The system must not claim real model reranking until a configured local reranker
executes without fallback.

## Accepted Boundary

Without a local model asset:

```text
MODEL_RERANKER_NOT_VERIFIED
```

With a complete local model asset and compatible runtime dependencies, the
operator may enable:

```text
RAG_RERANKER_TYPE=local-model
RAG_RERANKER_MODEL_PATH=<local external model directory>
```

No model files are committed to Git.
