# v2.0 Agent-RAG Phase 2 Index Lifecycle

Phase 2 implements a local single-process lifecycle:

```text
build candidate index
-> validate candidate
-> run smoke retrieval
-> mark ready
-> atomic activate
-> retain previous
-> rollback if needed
```

Implemented behavior:

- Candidate indexes are added to `LocalIndexRegistry`.
- `activate_index(version)` switches active version per tenant.
- The previous active version is retained.
- `rollback_index(tenant, previousVersion)` can reactivate a retired previous
  index.
- Failed or non-ready indexes cannot become active.
- V2 candidate build does not affect active V1 before activation.

Evidence:

- `ai-service/scripts/e2e/run_agent_rag_index_lifecycle_e2e.py`
- `artifacts/agent-rag/v2.0-phase2/index-lifecycle-e2e.json`

This is not a distributed index consistency protocol.
