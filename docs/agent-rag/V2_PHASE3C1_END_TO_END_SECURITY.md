# Phase 3C.1 End-to-End Security Governance

## Completed Capabilities

Phase 3C.1 now covers these security governance controls:

- PII redaction metadata stored on Agent-RAG runs;
- prompt-injection detection metadata stored on Agent-RAG runs;
- durable evidence, runtime, decision and audit hash lineage;
- tenant audit chain table and Java persistence;
- per-run integrity verification endpoint;
- global security status endpoint;
- evidence retention preview and bounded execution;
- safe JSON export endpoint;
- Admin security governance page.

## Admin Pages

The new security governance page is available at:

`/agent-rag/security`

It supports:

- viewing policy and audit-chain status;
- previewing expired evidence candidates;
- executing one retention batch;
- exporting a single run as sanitized JSON.

## Boundaries

The implementation does not:

- delete business data;
- expose raw evidence payloads through export;
- accept arbitrary SQL or external retention dates;
- change core Agent-RAG decision logic;
- claim production readiness;
- push, tag or release.

## Current Gate

The local maturity gate remains local-only. Production readiness is not claimed until deployment, backup, SSO, monitoring, distributed lock and operational runbook controls are independently verified.
