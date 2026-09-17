# v2.0 Agent-RAG Phase 2 Architecture

Phase 2 adds governed knowledge ingestion and hybrid retrieval:

```text
knowledge documents
-> validate
-> normalize
-> split
-> enrich metadata
-> deduplicate
-> sparse index
-> dense adapter
-> manifest
-> activate
```

Query path:

```text
query normalize
-> query analysis
-> multi-query recall
-> BM25 recall
-> dense recall
-> RRF fusion
-> tenant/time/status filter
-> evidence quality gate
-> deterministic/model-fallback rerank
-> Agent-RAG citations
```

Implemented files:

- `ai-service/app/agent_rag/knowledge.py`
- `ai-service/app/agent_rag/phase2_retrieval.py`
- `ai-service/scripts/evaluation/run_agent_rag_phase2_eval.py`
- `ai-service/scripts/e2e/run_agent_rag_index_lifecycle_e2e.py`
- `ai-service/scripts/readiness/run_agent_rag_phase2_gate.py`

The current benchmark mode is `fixture_hash_dense`. Real BGE-M3/FAISS and model
reranker quality are not claimed in this phase.
