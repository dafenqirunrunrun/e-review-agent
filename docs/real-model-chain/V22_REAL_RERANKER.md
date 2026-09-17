# v2.2 Real Reranker

## Model

| Item | Value |
| --- | --- |
| Model | `BAAI/bge-reranker-v2-m3` |
| Revision | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` |
| Provider | `FlagEmbedding.FlagReranker` |
| License | `Apache-2.0` |
| Candidate K | `12` |
| Final K | `5` default, runtime tests can narrow the request top K |
| Batch | `4` |
| Max length | `384` |

## Formal Runtime Integration

The formal reranker path now reads the external v2.2 asset manifest when
`AGENT_RAG_V22_ASSET_MANIFEST` is configured. The manifest provides the model
path, model id, revision and asset fingerprint. The true manifest remains
outside Git.

The runtime path is:

```text
AgentRagRuntime
-> GovernedReranker
-> LocalModelReranker
-> FlagEmbedding.FlagReranker.compute_score
```

## Evidence

Repository-safe evidence includes:

- requested/effective reranker type
- model id
- revision
- fingerprint prefix
- input/output counts
- duration
- fallback status and reason

It does not include:

- model absolute path
- full raw candidate text beyond normal citation snippets
- model weights
- Hugging Face cache

## Verification

| Check | Result |
| --- | --- |
| Standalone real smoke | `AGENT_RAG_V22_REAL_RERANKER_RUNTIME_PASS` |
| Formal runtime marker | `real_reranker_runtime`: `1 passed` |
| Reranker unit/regression file | `10 passed` |

## Remaining Qualification

`MODEL_RERANKER_NOT_VERIFIED` is still retained because the frozen benchmark,
Java E2E and 1800-second real model soak have not passed yet.
