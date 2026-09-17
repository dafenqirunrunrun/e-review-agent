# V2 Observability Architecture

The observability layer is intentionally local and dependency-light. It does not introduce a tracing platform, message queue, Redis, Kafka, Kubernetes, or production HA claim.

Runtime surfaces:

- Python FastAPI exposes `live`, `ready`, JSON metrics, and OpenMetrics text endpoints under `/api/v1/internal/agent-rag/*`.
- Java admin-api exposes `/admin/agent-rag/runtime/live`, `/runtime/ready`, and `/runtime/metrics`.
- The existing `/admin/agent-rag/health` response now includes runtime metrics in addition to AI Runtime and circuit breaker status.
- The Admin runtime page renders status, metrics, Provider, Index, and Circuit Breaker in a screenshot-friendly form.

Correlation:

- Java sends `X-Request-Id` and `X-Tenant-Id` when calling Python.
- Python rejects a request when `X-Request-Id` does not match the request body `requestId`.
- Python structured logs include request id, tenant id, and subject id from a context variable and redact sensitive fields.

Resilience:

- CUDA embedding calls pass through a local single-node GPU gate.
- Provider construction is cached by provider configuration to avoid repeated cold starts.
- FAISS active-index load and activation share a lock so readers do not observe partially swapped pointers.
