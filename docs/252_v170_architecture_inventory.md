# v1.7.0 Architecture Inventory

Status: `V170_ARCHITECTURE_INVENTORY_PASS`

This inventory was created before adding v1.7.0 enterprise components. Its purpose is to prevent duplicate implementations and to make the migration path explicit.

## Current Strengths

- FastAPI already exposes review, LLM, RAG v2, VLM, system, and agent-framework routers.
- RAG v2 already has lexical retrieval, dense embeddings, FAISS storage, hybrid retrieval, and reranker fallback.
- Local Qwen runtime already contains CUDA generation, GPU gate integration, schema parsing, and conservative repair behavior.
- Dataset access guard exists and must be reused by v1.7.0 builders and evaluators.
- External-test isolation and security hygiene scripts are already available.

## Enterprise Gaps

- Runtime configuration is not centralized across Base, Adapter, Shadow, RAG, Agent, cache, audit, and security controls.
- Adapter runtime is not behind a governed provider factory with validation, rollback, and shadow execution.
- RAG lacks document governance, tenant-aware versions, tombstones, incremental ingestion, and evidence verification.
- Agent orchestration needs bounded steps, registered read-only tools, policy guards, and human review routing.
- Idempotency, cache boundaries, privacy-safe logging, prompt injection defense, and observability need first-class modules.
- Enterprise API must be added beside existing APIs without breaking compatibility.

## Recommended Migration

1. Add v1.7.0 modules beside existing modules.
2. Preserve current `/review`, `/llm`, `/rag-v2`, and VLM routes.
3. Route new enterprise behavior through `/api/v1/e-review/*`.
4. Keep default model mode as `base`.
5. Enable adapter and shadow behavior only through explicit runtime configuration.
6. Reuse DatasetAccessGuard for any v1.7.0 evaluation scripts.

## Risk Notes

- The Qwen runtime and GPU gate are high-risk areas because they touch local CUDA resources.
- RAG migration is medium-risk because existing FAISS metadata must stay consistent.
- New security and observability modules should log only hashes and aggregate metadata.
- No v1.7.0 task may reopen or recompute the closed v2.3 holdout.
