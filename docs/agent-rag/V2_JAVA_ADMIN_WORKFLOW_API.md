# V2 Java Agent-RAG Admin Workflow API

## Scope

The Java admin API exposes the governed Agent-RAG workflow through litemall
admin authentication and the existing AI review permissions. It does not replace
the older AI review pages and does not change existing litemall business APIs.

Base path:

```text
/admin/agent-rag
```

## Endpoints

### Health

```http
GET /admin/agent-rag/health
```

Checks the Java client connection to the configured Agent-RAG runtime health
endpoint.

Permission:

```text
admin:ai:review:list
```

### Analyze

```http
POST /admin/agent-rag/analyze
```

Creates a durable workflow run, calls the Agent-RAG runtime, stores the final
run status and bounded evidence bundle, then returns the persisted run.

Permission:

```text
admin:ai:review:analyze
```

Important behavior:

- the trusted tenant resolver overwrites any client-supplied tenant ID;
- idempotency prevents duplicate runs for the same governed analysis profile;
- failures are persisted as `FAILED` and returned with an Agent-RAG error code;
- evidence is bounded and redacted before storage.

### Runs

```http
GET /admin/agent-rag/runs?status=SUCCESS&limit=20
GET /admin/agent-rag/runs/{id}
```

Lists recent runs or returns one run with its evidence record.

Permission:

```text
admin:ai:review:list
```

### Evidence

```http
GET /admin/agent-rag/runs/{id}/evidence
```

Returns the bounded persisted evidence bundle for a run.

Permission:

```text
admin:ai:review:list
```

### Replay

```http
POST /admin/agent-rag/runs/{id}/replay
```

Creates a new run with `replay_of_run_id` pointing to the original run. The old
run is not overwritten.

Permission:

```text
admin:ai:review:analyze
```

### Human Override

```http
POST /admin/agent-rag/override
```

Appends a human override record. It does not overwrite the machine decision.

Permission:

```text
admin:ai:review:analyze
```

Example body:

```json
{
  "runId": 1,
  "newRiskLevel": "medium",
  "newAction": "manual_review",
  "reason": "Operator reviewed the evidence and adjusted the risk boundary.",
  "operatorId": 1
}
```

## Local Gate Script

Script:

```text
scripts/e-review-java-agent-rag-workflow-gate.ps1
```

Checks:

- admin login;
- Agent-RAG health through the Java client;
- governed analyze workflow;
- persisted run detail;
- persisted evidence with bundle hash;
- append-only human override.

Expected final token:

```text
JAVA_AGENT_RAG_WORKFLOW_GATE_PASS
```

The script requires the SQL migration to be applied and the admin API plus
Agent-RAG runtime to be running.
