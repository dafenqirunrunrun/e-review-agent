# V2 Admin Operations Architecture

## Scope

This phase adds a management-facing Agent-RAG operations center for local
single-node enterprise-maturity validation. It does not change the core
Agent-RAG workflow, retrieval provider, model runtime, database schema, or
production-readiness boundary.

## Flow

```text
Admin UI
-> src/api/agentRag.js
-> /admin/agent-rag/*
-> AdminAgentRagController
-> AgentRagWorkflowService
-> litemall_agent_rag_run / evidence / override
-> FastAPI Agent-RAG runtime for analyze/replay
```

## Backend Additions

- `GET /admin/agent-rag/overview` returns bounded operational statistics for a
  tenant-scoped time window.
- `GET /admin/agent-rag/runs` supports filters, pagination, effective decision
  projection, override counts, provider fields, fallback fields, and duration.
- `GET /admin/agent-rag/runs/{id}/compare/{otherRunId}` returns lightweight
  replay comparison deltas without embedding full evidence bundles.

## Frontend Modules

- `overview.vue`: operational metrics, distributions, recent failures, pending
  reviews, runtime state.
- `runs/index.vue`: multi-condition query, quick filters, pagination, table
  actions, override and replay entry points.
- `detail.vue`: original/effective decision, runtime metadata, bounded
  evidence timeline, override history, replay comparison.
- `runtime.vue`: provider/index/circuit-breaker status with optional 30-second
  refresh.

## Boundaries

The UI is read/write only for append-only override and replay operations.
It does not expose index upload/switching, circuit-breaker mutation, prompt
contents, model paths, database credentials, or raw unbounded evidence.
