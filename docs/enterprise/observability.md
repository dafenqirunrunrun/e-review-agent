# Observability

The v1.7.0 layer includes privacy-safe spans and metrics for:

- request
- input guard
- routing
- query rewrite
- sparse retrieval
- dense retrieval
- fusion
- rerank
- evidence verification
- model generation
- policy guard
- response
- audit

Metrics include requests, success, fallback, human review, prompt injection, tool failure, rollback, latency, queue depth, cache hit rate, and schema valid rate. The local implementation exposes JSON metrics through `/api/v1/e-review/metrics`.
