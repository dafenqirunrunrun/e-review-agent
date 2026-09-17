# v2.0 Agent-RAG Phase 1 Request And Result Contract

## Request

Required fields:

- `requestId`
- `tenantId`
- `subjectType`
- `subjectId`
- `query`
- `runtimeMode`
- `schemaVersion`

Retrieval options:

- `enabled`
- `topK`
- `rerankTopK`
- `minScore`
- `publicTenantEnabled`

Rules:

- Missing tenant ID is rejected.
- Unsupported schema versions are rejected.
- Internal model paths, prompts, tokens, and private raw documents are not
  returned.
- `requestId` is preserved in the result, trace, and evidence bundle.
- `subjectId` participates in idempotency with tenant, analyzer version, and
  index version.

## Result

The result includes:

- `decision`: risk level, risk types, and action.
- `analysis`: summary and confidence.
- `retrieval`: query trace, topK, citations, index version, embedding model,
  and empty-retrieval flag.
- `runtime`: engine type, model name, fallback status, analyzer version, schema
  version, repair attempts, and validation errors.
- `audit`: timing, Agent path, and evidence ID.

Each citation contains document ID, chunk ID, tenant ID, source type, title,
score, rank, content hash, and a bounded snippet.
