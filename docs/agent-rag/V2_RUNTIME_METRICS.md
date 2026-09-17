# V2 Runtime Metrics

Python metrics:

- `requests_total`
- `success_total`
- `fallback_total`
- `risk_task_total`
- `idempotency_hit_total`
- `request_latency_ms`
- `embedding_latency_ms`
- `faiss_search_latency_ms`
- `index_load_latency_ms`
- `gpu_queue_timeout_total`
- `gpu_in_flight`

Endpoints:

- `GET /api/v1/internal/agent-rag/metrics`
- `GET /api/v1/internal/agent-rag/metrics/openmetrics`

Java metrics:

- `requestsTotal`
- `successTotal`
- `failureTotal`
- `fallbackTotal`
- `idempotencyHitTotal`
- latency count/min/max/p95

Endpoints:

- `GET /admin/agent-rag/runtime/metrics`
- Included in `GET /admin/agent-rag/health`

Notes:

- Metrics are in-memory and intended for local graduation-project runtime validation.
- Metrics reset on process restart and are not claimed as production observability storage.
