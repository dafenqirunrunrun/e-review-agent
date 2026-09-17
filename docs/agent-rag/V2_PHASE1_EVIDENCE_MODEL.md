# v2.0 Agent-RAG Phase 1 Evidence Model

Each full analysis creates an `AgentRagEvidenceBundle` containing:

- `evidenceId`
- `requestId`
- `tenantId`
- `subjectId`
- `sourceCommit`
- `runtimeMode`
- `schemaVersion`
- `analyzerVersion`
- `indexVersion`
- `retrievalEvidence`
- `agentTrace`
- `decision`
- `timing`
- `errors`

Trace steps record node name, start/end time, status, input hash, output hash,
and error code. They intentionally do not record passwords, API tokens, model
weight paths, full system prompts, or unbounded private source text.

The evidence bundle supports audit, replay, debugging, and result comparison.
It is a Phase 1 local artifact and is not a production evidence store.
