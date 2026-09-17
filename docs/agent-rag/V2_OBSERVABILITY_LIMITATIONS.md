# V2 Observability Limitations

The phase intentionally avoids production infrastructure claims.

Current limitations:

- Metrics are in-memory and reset on process restart.
- Logs are structured but not shipped to a centralized log platform.
- Trace correlation uses request id headers and structured fields, not a distributed tracing backend.
- GPU concurrency protection is process-local.
- FAISS hot swap locking is process-local.
- Load and soak scripts validate local stability only.
- No Kafka, Redis, Kubernetes, Prometheus server, Grafana, or OpenTelemetry collector is required.

Accepted value for this project:

- The system has observable local runtime state.
- Java/Python requests can be correlated.
- Degraded mode is explicit instead of silent.
- Demo operators can inspect runtime status from the Admin UI.
