# v2.0 Agent-RAG Phase 2 Limitations

Verified:

- Knowledge document and chunk contracts.
- Ingestion validation, deduplication, and manifest generation.
- BM25 recall.
- Hash dense adapter recall for fixture-mode comparison.
- RRF fusion with rank-only signals.
- Tenant, status, and time validity filtering.
- Evidence quality gate.
- Pluggable reranker interface and deterministic fallback.
- Local index activation and rollback.
- 120-case fixture benchmark.

Not verified:

- Trained reranker quality.
- BGE-M3 + FAISS quality in this Phase 2 gate.
- Million-scale knowledge base.
- Multi-process index consistency.
- Multi-node vector database.
- Production concurrency.
- Online knowledge approval workflow.
- Formal Enterprise RAG production readiness.
- Production release.
