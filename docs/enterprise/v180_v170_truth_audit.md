# v1.8.0 Truth Audit of v1.7.0

Status: `V170_ENGINEERING_GATE_DOWNGRADED_DEMO_ONLY`

## Downgrade Reasons

- Enterprise dense retrieval uses HashDenseRetriever instead of a real local embedding model.
- Enterprise evaluation reports perfect metrics from deterministic programmatic functions.
- v1.7 corpus and query generation are coupled and leakage resistance is unproven.

## Classifications

- Dense Retriever: `HASH_DEMO_ONLY`
- Sparse Retriever: `PARTIAL_IMPLEMENTATION`
- Hybrid: `PARTIAL_IMPLEMENTATION`
- Reranker: `PARTIAL_IMPLEMENTATION`
- Agent: `PARTIAL_IMPLEMENTATION`
- Tool Registry: `PARTIAL_IMPLEMENTATION`
- PII: `PARTIAL_IMPLEMENTATION`
- Logging: `PARTIAL_IMPLEMENTATION`
- Idempotency: `PARTIAL_IMPLEMENTATION`
- Cache: `IN_MEMORY_ONLY`
- Circuit Breaker: `UNIT_TEST_ONLY`
- Shadow: `PARTIAL_IMPLEMENTATION`
- API: `PARTIAL_IMPLEMENTATION`
- Metrics: `IN_MEMORY_ONLY`
- Docker: `PARTIAL_IMPLEMENTATION`
- Tests: `UNIT_TEST_ONLY`
- Enterprise Eval: `MOCK_ONLY`

## Boundary

- Closed holdouts accessed: `false`
- Adapter published: `false`
- Training executed: `false`

This audit intentionally downgrades demo-only evidence instead of preserving inflated readiness claims.
