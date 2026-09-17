# V2 Runtime Readiness

Python endpoints:

- `GET /api/v1/internal/agent-rag/live`: process liveness.
- `GET /api/v1/internal/agent-rag/ready`: runtime readiness or degraded status with Provider, Index, and GPU gate snapshot.
- `GET /api/v1/internal/agent-rag/dense/health`: dense Provider and Index compatibility health.

Java endpoints:

- `GET /admin/agent-rag/runtime/live`
- `GET /admin/agent-rag/runtime/ready`
- `GET /admin/agent-rag/health`

Readiness semantics:

- `ready`: Runtime is reachable and required Provider/Index signals are acceptable.
- `degraded`: Runtime is reachable but Provider fallback, missing active index, or compatibility uncertainty exists.
- `unavailable`: Java client cannot reach or parse the Runtime health response.

This phase does not convert degraded mode into a production SLO. It only makes local state explicit for acceptance and demonstration.
