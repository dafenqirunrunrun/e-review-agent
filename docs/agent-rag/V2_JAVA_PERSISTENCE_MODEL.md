# V2 Java Agent-RAG Persistence Model

## Scope

This document freezes the Java-side durable workflow model for the governed
Agent-RAG runtime. It covers persistence, idempotency, evidence capture, replay,
and human override boundaries. It does not claim production HA, distributed
locking, real LLM quality, or model reranking.

## SQL Migration

Migration file:

```text
litemall-db/sql/litemall_agent_rag_workflow.sql
```

Tables:

- `litemall_agent_rag_run`: one row per governed Agent-RAG workflow run.
- `litemall_agent_rag_evidence`: bounded and redacted evidence bundle for a
  completed run.
- `litemall_agent_rag_override`: append-only human override records.

Important constraints:

- `uk_agent_rag_run_tenant_request`: prevents duplicate request IDs inside a
  tenant.
- `uk_agent_rag_run_idem`: prevents repeated analysis for the same governed
  idempotency profile.
- `uk_agent_rag_evidence_run`: keeps one evidence bundle per run.

Rollback is documented in SQL comments. Existing litemall business tables are
not modified.

## Java Model

New DB domain and mapper files:

- `LitemallAgentRagRun`
- `LitemallAgentRagEvidence`
- `LitemallAgentRagOverride`
- `LitemallAgentRagRunMapper`
- `LitemallAgentRagEvidenceMapper`
- `LitemallAgentRagOverrideMapper`

Service wrappers:

- `LitemallAgentRagRunService`
- `LitemallAgentRagEvidenceService`
- `LitemallAgentRagOverrideService`

The admin workflow entry point is:

```text
org.linlinjava.litemall.admin.service.agentrag.AgentRagWorkflowService
```

## Workflow States

Current durable states:

- `RUNNING`: run row has been created and the HTTP call is in progress.
- `SUCCESS`: model/RAG result passed validation and does not require manual
  review.
- `RULE_FALLBACK`: runtime reported a fallback path.
- `REVIEW_REQUIRED`: Agent-RAG result requires human review.
- `FAILED`: HTTP, protocol, tenant, timeout, circuit, or serialization failure.

The workflow intentionally avoids one long transaction around the HTTP call.
The initial run is inserted first, the external call happens outside the DB
operation, and the final state/evidence is persisted afterward.

## Idempotency

The Java workflow computes a SHA-256 idempotency key from:

- trusted tenant ID;
- subject type;
- subject ID;
- schema version;
- runtime mode;
- requested retrieval mode;
- parent run ID;
- replay source run ID.

This prevents accidental duplicate Agent-RAG decisions while still allowing
explicit replay records to be distinguished.

## Evidence Bundle

The evidence bundle captures:

- request identity;
- subject identity;
- decision;
- analysis;
- retrieval metadata and citations;
- runtime metadata;
- audit metadata.

The persisted bundle is bounded by `agent-rag.max-evidence-bytes`.
When the full bundle exceeds the limit, the stored JSON remains valid and
contains a truncated prefix plus the original SHA-256.

Redaction rules remove or mask sensitive keys and local paths, including token,
secret, authorization, password, prompt, model path, and filesystem path fields.

## Human Override

Human override records are append-only. A new row records:

- original risk/action snapshot;
- new risk/action;
- operator ID;
- explicit reason;
- timestamp.

The original Agent-RAG run decision is not overwritten by the override insert.
Downstream admin APIs can present the latest override while preserving the
original machine decision for audit.

## Replay

Replay creates a new run with `replay_of_run_id` pointing to the original run.
The original run is not overwritten. This preserves evaluation lineage and lets
operators compare old and new results.

## Tests

Targeted command:

```powershell
mvn -pl litemall-admin-api -am -Dtest=*AgentRag* -DfailIfNoTests=false test
```

Observed result:

```text
BUILD SUCCESS
Tests run: 19, Failures: 0, Errors: 0, Skipped: 0
```

The new persistence tests verify:

- stable tenant-scoped idempotency key behavior;
- evidence redaction for local paths and sensitive keys;
- valid JSON output after evidence bounding/truncation.

## Boundaries

Still not claimed:

- distributed workflow lock;
- async queue execution;
- high-availability persistence;
- production-scale concurrency;
- model reranker verification;
- real LLM quality verification.
