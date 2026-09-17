# v2.0 Agent-RAG Phase 2 Retrieval Evaluation

Benchmark:

- Fixture path: `ai-service/tests/fixtures/agent_rag/phase2/corpus.json`
- Generated cases: 120
- Mode: `fixture_hash_dense`
- Real embedding mode: false
- Model reranker mode: false

Current metrics from the Phase 2 gate:

- BM25 Recall@5: 0.70
- Dense Recall@5: 0.70
- Hybrid Recall@5: 0.70
- Hybrid MRR: 0.645833
- Hybrid nDCG@5: 0.660017
- Hybrid + reranker nDCG@5: 0.663093
- Citation coverage: 0.70
- Tenant violations: 0
- Expired evidence violations: 0
- Duplicate evidence rate: 0

Latency is reported only for fixture/hash dense mode:

- Retrieval p50: about 0.7 ms
- Retrieval p95: about 0.9 ms
- Model reranker: `MODEL_RERANKER_NOT_MEASURED`

The Phase 2 gate records a fixture-mode Hybrid MRR tolerance of `0.03` because
hash dense rank variance is not a real embedding quality signal.
