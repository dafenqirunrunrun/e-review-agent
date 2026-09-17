# v2.0 Agent-RAG Phase 1 Implementation Audit

## Existing And Reusable

- Agent orchestration exists in `ai-service/app/agent/` and
  `ai-service/app/agent_framework/`.
- Tenant normalization and ACL logic exist in `ai-service/app/rag/tenant_acl.py`.
- Sparse, dense, hybrid retrieval, reranking hooks, evidence verification, and
  FAISS versioning primitives exist in `ai-service/app/rag/`.
- The canonical decision contract exists in
  `ai-service/app/contracts/e_review_decision.py`.
- Rule fallback and provider factory behavior exists in
  `ai-service/app/llm/enterprise_providers.py`.
- v1.8.x documents record BGE-M3, FAISS, tenant-isolation, and benchmark
  evidence boundaries.

## Existing But Incomplete

- Existing Agent state traces are useful but not shaped as a replayable
  Agent-RAG evidence bundle.
- Existing RAG code has tenant filtering, but Phase 1 needs a single auditable
  request/result contract around it.
- Existing enterprise API records RAG request counters, but the unified
  Agent-RAG result shape is not exposed as a single Phase 1 object.
- Existing benchmark material is broad; Phase 1 needs a small reproducible
  fixture with explicit tenant, fallback, citation, and duplicate cases.

## Added In This Phase

- `ai-service/app/agent_rag/`: unified request/result contracts, governed
  retrieval, deterministic rerank, fallback, evidence bundle, and in-memory
  idempotency for Phase 1.
- `ai-service/tests/fixtures/agent_rag/phase1_cases.json`: project-owned
  synthetic fixture with 30 cases.
- Evaluation, E2E, and readiness gate scripts under `ai-service/scripts/`.
- Phase 1 documentation under `docs/agent-rag/`.

## Explicitly Out Of Scope

- Model training, SFT, LoRA, quantization, VLM experiments, Qdrant, Milvus,
  Elasticsearch, Kafka, Kubernetes, large database migrations, public repo
  synchronization, releases, and tags.
