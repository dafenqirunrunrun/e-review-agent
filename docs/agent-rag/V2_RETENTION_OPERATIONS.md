# Agent-RAG Retention Operations

## Scope

This document describes the local single-node retention controls added for Agent-RAG enterprise maturity.

Retention is limited to Agent-RAG evidence payloads:

- `litemall_agent_rag_evidence.bounded_json`
- `litemall_agent_rag_evidence.payload_size_bytes`
- `litemall_agent_rag_evidence.evidence_expired`
- `litemall_agent_rag_evidence.expired_at`

The operation does not delete litemall business rows, model files, indexes, logs, or audit hashes.

## Policy

Evidence payloads become retention candidates when the owning run has:

- matching tenant;
- `deleted = 0`;
- `evidence_expires_at` set;
- `evidence_expires_at <= now`;
- evidence not already expired.

The run-level audit metadata remains available after expiry:

- `bundle_hash`;
- `citation_set_hash`;
- `runtime_config_hash`;
- `effective_decision_hash`;
- `previous_audit_hash`;
- `audit_hash`;
- `audit_integrity_status`.

## APIs

### Status

`GET /admin/agent-rag/security/retention/status`

Permission: `admin:agentRag:retention`

Returns the current tenant, pending expired evidence count, batch limit and policy summary.

### Preview

`POST /admin/agent-rag/security/retention/preview`

Permission: `admin:agentRag:retention`

Body:

```json
{
  "limit": 50
}
```

The preview is a dry run. It returns candidate IDs and hashes only.

### Execute

`POST /admin/agent-rag/security/retention/execute`

Permission: `admin:agentRag:retention`

Body:

```json
{
  "limit": 50
}
```

The execute endpoint processes one bounded batch. The maximum accepted batch limit is 100. It replaces each expired evidence payload with an expiry marker and preserves hash lineage.

## Operational Boundaries

- No arbitrary SQL is accepted from the UI or API.
- No caller-provided cutoff date is accepted.
- No business table delete is performed.
- No raw evidence payload is exported by retention endpoints.
- Tenant scope is resolved server-side.

## Verification

Run:

```powershell
D:\anaconda\envs\torchtest-phase3a3-tf4\python.exe scripts\readiness\run_agent_rag_phase3c1_retention_export_gate.py
```

Expected markers:

- `AGENT_RAG_RETENTION_API_PASS`
- `AGENT_RAG_RETENTION_BOUNDARY_PASS`
- `AGENT_RAG_SECURE_EXPORT_API_PASS`
- `AGENT_RAG_ADMIN_SECURITY_UI_PASS`
