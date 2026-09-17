# v2.0 Agent-RAG Phase 1 Architecture

Phase 1 implements one governed local chain:

```text
review/risk input
-> request validation
-> tenant normalization
-> intent classification
-> tenant-scoped retrieval
-> deterministic rerank and deduplicate
-> Agent analysis
-> rule validation
-> risk decision
-> evidence bundle
-> replayable result
```

Actual implementation:

- Request and result contracts: `ai-service/app/agent_rag/contracts.py`
- Runtime chain: `ai-service/app/agent_rag/runtime.py`
- Tenant filtering: candidate generation includes only the request tenant and
  optional `__public__` chunks.
- Retrieval: local BM25/HybridRetriever over Phase 1 fixture chunks.
- Rerank: deterministic trust and score ordering. It is not claimed as a
  trained reranker.
- Fallback: explicit rule fallback when model runtime is unavailable or model
  output is invalid.
- Evidence: every result includes citations and an evidence bundle with hashed
  trace inputs/outputs.

This phase does not claim production Enterprise RAG. It proves the governed
runtime contract and gate mechanics on a reproducible local fixture.
