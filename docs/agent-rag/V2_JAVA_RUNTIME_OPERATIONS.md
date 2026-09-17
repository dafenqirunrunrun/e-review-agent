# V2 Java Runtime Operations

## Scope

This document describes local single-node operations for the Java Agent-RAG
runtime acceptance environment. It is for internal validation and demonstration,
not production deployment.

## Services

```text
MySQL: local litemall schema
AI runtime: 127.0.0.1:8008
admin-api: 127.0.0.1:8083
```

## Startup Order

1. Start local MySQL and confirm the `litemall` schema is reachable.
2. Apply `litemall-db/sql/litemall_agent_rag_workflow.sql` if the Agent-RAG
   workflow tables do not exist.
3. Start the AI runtime on `127.0.0.1:8008`.
4. Confirm dense health:

```text
GET /api/v1/internal/agent-rag/dense/health
expected status: ready
expected provider: flagembedding
expected indexCompatible: true
expected fallbackUsed: false
```

5. Start `litemall-admin-api` on `127.0.0.1:8083`.
6. Confirm admin Agent-RAG health:

```text
GET /admin/agent-rag/health
expected runtime.status: ready
expected circuitBreaker.state: CLOSED
```

## Stop Order

1. Stop `litemall-admin-api`.
2. Stop the AI runtime.
3. Keep MySQL running unless the whole local environment is being stopped.

## Runtime Gate Order

```text
scripts/readiness/run_agent_rag_database_migration_gate.py
scripts/readiness/run_agent_rag_ai_runtime_gate.py
scripts/readiness/run_agent_rag_admin_runtime_gate.py
scripts/e-review-java-agent-rag-workflow-gate.ps1
scripts/readiness/run_agent_rag_java_runtime_gate.py
```

## Common Errors

### AI Runtime Health Is Degraded

Check whether the dense provider has loaded and whether the active FAISS index
metadata matches the effective embedding fingerprint. Do not fall back to hash
retrieval for Java Runtime Acceptance.

### Admin Health Is Unavailable

Confirm the admin-api is running on port `8083`, Agent-RAG is enabled, and the
configured base URL points to the local AI runtime.

### Replay Request ID Mismatch

Replay must create a new Java run and the AI runtime must return the current
request ID. Runtime result caching must not reuse an older result for a new
replay request.

### Circuit Breaker Does Not Open

Use a unique test subject prefix for each workflow gate run. Reusing old subject
IDs can trigger Java idempotency and avoid real downstream calls, which means
the breaker will not accumulate failures.

## Boundaries

```text
NO_PUSH
NO_TAG
NO_RELEASE
ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED
MODEL_RERANKER_NOT_VERIFIED
REAL_LLM_QUALITY_NOT_VERIFIED
```
