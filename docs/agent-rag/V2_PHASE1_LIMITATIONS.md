# v2.0 Agent-RAG Phase 1 Limitations

Verified in this phase:

- Unified request and result contracts.
- Tenant-scoped retrieval over a reproducible local fixture.
- Bounded citations.
- Deterministic rerank and deduplication.
- Explicit fallback when model runtime is unavailable or invalid.
- Replayable evidence bundle.
- Offline evaluation, business E2E, and readiness gate.

Not verified in this phase:

- Private model quality.
- Large real knowledge base quality.
- Production concurrency.
- Multi-node deployment.
- High-availability vector database.
- Formal Enterprise RAG production readiness.
- Real production release.

Current retrieval uses a local fixture and existing retriever primitives. BGE-M3
and FAISS capabilities remain documented from previous internal evidence but
are not newly revalidated by this Phase 1 gate.
