# Real Model Chain

Classification: `BLOCKED`

This stage did not execute the real model chain gate because the formal reranker runtime remains blocked.

The next real model chain validation must only proceed after:

- `FlagEmbedding==1.4.0` import smoke passes
- Formal reranker runtime test passes
- Phase 3B formal gate reports real FlagEmbedding provider, model loaded, and no fallback
- Qwen regression remains real generate and schema-valid
- v2.4 trace/replay regression remains green

Until then, the correct boundary is:

```text
REAL_RERANKER_RUNTIME_BLOCKED
QUALITY_EVALUATION_NOT_RUN
REAL_MODEL_CHAIN_BLOCKED
```
