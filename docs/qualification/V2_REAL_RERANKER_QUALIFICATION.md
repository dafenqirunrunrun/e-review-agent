# v2.1 Real Reranker Qualification

## Objective

This module evaluates whether a real local reranker can replace or augment the
deterministic reranker path in the v2.1 qualification branch. It does not modify
the locked v2.0 RC baseline at `ffd05f26`.

## Existing Implementation Audit

The repository already contains a governed reranker path:

- `ai-service/app/agent_rag/reranker.py` contains `LocalModelReranker`.
- `RerankerService` can select the local model provider when configured.
- `scripts/readiness/run_agent_rag_phase3b_gate.py` already emits
  `AGENT_RAG_MODEL_RERANKER_BLOCKED` when the model is unavailable.
- `tests/test_v200_agent_rag_phase3b_reranker.py` contains the real reranker
  marker and skips it when no local model asset is available.

No reranker architecture rewrite was performed in this qualification step.

## Asset Status

The offline model asset audit produced:

- Asset type: `reranker`
- Environment variable: `RAG_RERANKER_MODEL_PATH`
- Available: `false`
- Blocker: `ENV_PATH_NOT_SET`
- Asset fingerprint: `null`

Because the required model path is not configured, the campaign must not attempt
runtime loading, score generation, benchmark comparison, or default-provider
promotion.

## Test Result

Executed:

```text
python -m pytest -ra -m real_reranker
```

Result:

```text
1 skipped, 498 deselected
```

Skip reason:

```text
RERANKER_MODEL_ASSET_UNAVAILABLE_SKIP
```

## Decision

```text
AGENT_RAG_MODEL_RERANKER_BLOCKED
MODEL_RERANKER_NOT_VERIFIED
```

The deterministic reranker remains the default path. This is a truthful
qualification blocker, not a failure of the v2.0 RC baseline.
