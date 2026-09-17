# V2 Structured Logging

Python Runtime:

- Module: `ai-service/app/agent_rag/observability.py`
- Log event format defaults to JSON.
- Request context uses `ContextVar` so concurrent requests do not share trace fields.
- Sensitive keys such as token, secret, password, authorization, prompt, and model path are redacted.
- Local Windows and Unix-like filesystem paths are replaced with `[redacted-path]`.

Java Runtime:

- `AgentRagWorkflowService` writes request id, tenant id, subject id, and run id into MDC.
- Workflow start, idempotency hit, success, and failure events are logged.
- MDC is cleared on the main success and failure paths to avoid thread-local leakage.

Trace contract:

- Java request body `requestId` and `X-Request-Id` must match.
- Python returns `400 AGENT_RAG_REQUEST_ID_HEADER_MISMATCH` when they differ.

Gate coverage:

- Python unit test validates log redaction and trace mismatch rejection.
- Java client contract test validates outgoing trace headers.
