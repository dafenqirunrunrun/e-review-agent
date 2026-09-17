# Agent-RAG Secure Export API

## Purpose

The secure export API provides a controlled JSON evidence package for audit review, thesis demonstration and local incident analysis without exposing raw bounded evidence payloads.

Endpoint:

`POST /admin/agent-rag/runs/{id}/export`

Permission:

`admin:agentRag:export`

## Export Contents

The response includes:

- run metadata;
- original machine decision fields;
- provider, retrieval and runtime identifiers;
- PII and prompt-injection governance metadata;
- audit hash lineage;
- evidence metadata;
- override hash lineage;
- integrity verification result;
- bounded evidence summary.

The response does not include:

- `boundedJson` raw content;
- raw business table rows;
- model paths;
- local filesystem paths;
- private model checkpoints;
- unredacted override reason text.

## Example Response Shape

```json
{
  "schemaVersion": "agent-rag-secure-export-v1",
  "rawEvidenceExported": false,
  "tenantId": "default",
  "run": {
    "id": 1,
    "requestId": "req-demo",
    "riskLevel": "high",
    "action": "manual_review",
    "auditHash": "..."
  },
  "evidence": {
    "available": true,
    "evidenceId": "ev-demo",
    "bundleHash": "...",
    "evidenceExpired": false
  },
  "overrideHistory": [],
  "integrity": {
    "status": "VALID",
    "valid": true
  },
  "boundedSummary": {
    "rawEvidenceIncluded": false,
    "hasRetrieval": true,
    "hasAnalysis": true
  }
}
```

## Audit Rationale

The API separates audit lineage from raw payload disclosure. This keeps the system demonstrable and auditable while honoring privacy and retention boundaries.

## Verification

The local gate checks that controller endpoints, permissions, UI API calls and test assertions all exist, and that the Java unit test verifies `rawEvidenceExported=false`.
