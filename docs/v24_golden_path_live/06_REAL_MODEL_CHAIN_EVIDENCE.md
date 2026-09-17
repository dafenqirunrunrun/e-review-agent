# Real Model Chain Evidence

REAL_BGE_M3_USED: true

REAL_FAISS_USED: true

REAL_RERANKER_USED: true

REAL_QWEN_USED: true

RULE_FALLBACK_USED: false

HASH_PROVIDER_USED: false

MOCK_PROVIDER_USED: false

## Evidence

- Dense health: `runtime-evidence/model/dense_health_after_agent_rag_live.json`.
- Live FAISS build: `runtime-evidence/model/live_faiss_index_build.json`.
- Main Agent-RAG run: `runtime-evidence/http/admin_agent_rag_analyze_comment_1015_live_faiss_fresh.json`.
- Metrics after run: `runtime-evidence/model/agent_rag_metrics_after_live.json`.

## Runtime Facts

- Embedding provider: `bge-m3`, implementation `flagembedding`, library `FlagEmbedding 1.3.5`.
- Embedding dimension: `1024`.
- FAISS index: `IndexFlatIP`, active version `v24-golden-live-20260728T064951Z`, vector count `9`.
- Reranker: `BAAI/bge-reranker-v2-m3`, candidate count `3`, output count `3`, duration `2156 ms`, fallback false.
- LLM: `Qwen/Qwen3-1.7B`, `Qwen3ForCausalLM`, structured output valid, duration `10989 ms`, fallback false.
- Main run: run `4`, evidence `06109824d6541a3ef51df684`, risk level `high`, action `create-risk-task`, confidence `0.9`.

## Warning

The response field `retrieval.indexVersion` remains `phase1-fixture-index-v1`; the live health endpoint and FAISS manifest confirm the actually loaded ACTIVE index is `v24-golden-live-20260728T064951Z`.
