# V2 Java Runtime Acceptance

## Scope

This phase validates the Java Agent-RAG workflow at runtime: database migration,
FastAPI runtime, admin-api runtime, Java-to-FastAPI HTTP calls, persistence,
idempotency, override, replay, and circuit-breaker behavior.

It does not claim production high availability, large-scale concurrency, model
reranking quality, or real LLM quality.

## Repository Baseline

```text
branch: experiment/v2.0-agent-rag-governed-runtime
starting HEAD: c61cc6cd
push: NO_PUSH
tag: NO_TAG
release: NO_RELEASE
```

Known unrelated working-tree items remain protected and must not be committed.

## Runtime Configuration Audit

Admin API:

```text
module: litemall-admin-api
port: 8083
active profiles: db, core, admin
Agent-RAG base URL: http://127.0.0.1:8008
analyze path: /api/v1/agent-rag/analyze
health path: /api/v1/internal/agent-rag/dense/health
single tenant: __local__
```

AI runtime:

```text
module: ai-service
FastAPI import path: app.main:app
target host: 127.0.0.1
target port: 8008
health endpoint: /api/v1/health
Agent-RAG dense health endpoint: /api/v1/internal/agent-rag/dense/health
```

Database:

```text
schema: litemall
configuration source: litemall-db application-db profile
connection details: local MySQL, credentials omitted
```

## Migration Status

```text
status: PASS
SQL file: litemall-db/sql/litemall_agent_rag_workflow.sql
backup: completed outside repository before migration
```

## Runtime Gate Status

```text
database gate: PASS
AI runtime gate: PASS
admin runtime gate: PASS
workflow gate: PASS
Java runtime gate: PASS
```

## Gate Evidence

The runtime acceptance produced the following local evidence files:

```text
artifacts/agent-rag/v2.0-java-runtime/database-migration-summary.json
artifacts/agent-rag/v2.0-java-runtime/ai-runtime-summary.json
artifacts/agent-rag/v2.0-java-runtime/admin-runtime-summary.json
artifacts/agent-rag/v2.0-java-runtime/java-workflow-runtime-summary.json
artifacts/agent-rag/v2.0-java-runtime/java-runtime-gate-summary.json
```

Final Java workflow summary:

```text
caseCount: 13
passed: 13
failed: 0
tenantViolations: 0
duplicateRuns: 0
duplicateEvidence: 0
duplicateRiskTasks: 0
overridePreservedOriginal: true
replayCreatedNewRun: true
circuitBreakerOpened: true
circuitBreakerRecovered: true
```

## Acceptance Tokens

```text
AGENT_RAG_DATABASE_MIGRATION_PASS
AGENT_RAG_AI_RUNTIME_PASS
AGENT_RAG_ADMIN_API_RUNTIME_PASS
AGENT_RAG_JAVA_HTTP_INTEGRATION_PASS
AGENT_RAG_RUNTIME_PERSISTENCE_PASS
AGENT_RAG_RUNTIME_IDEMPOTENCY_PASS
AGENT_RAG_RUNTIME_OVERRIDE_PASS
AGENT_RAG_RUNTIME_REPLAY_PASS
AGENT_RAG_RUNTIME_CIRCUIT_BREAKER_PASS
AGENT_RAG_JAVA_WORKFLOW_RUNTIME_PASS
```

## Regression Results

```text
pip check: PASS
Python pytest: 464 passed, 11 skipped
Python real_dense marker: 1 passed, 7 skipped, 467 deselected
Java Agent-RAG targeted tests: 20 passed
Maven package: PASS
Full Maven test: FAIL due pre-existing litemall-core storage/PowerMock tests
```

Full Maven test failures remained outside this phase:

```text
AliyunStorageTest.test: third-party object storage initialization
QiniuStorageTest.test: missing test resource
TencentStorageTest.test: missing test resource / remote bucket issue
BCryptTest.initializationError: PowerMock/Objenesis access issue on current JDK
```

These failures were not introduced by the Java Agent-RAG runtime acceptance
changes and were not bypassed.
