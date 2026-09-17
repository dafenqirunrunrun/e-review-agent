# v1.8.0 Observability Real Signals

Status: `V180_OBSERVABILITY_REAL_SIGNALS_PASS`

## Implemented Signals

- Request, success, RAG request, prompt-injection, and idempotency-hit counters.
- Request latency, model latency, and PII redaction histograms.
- Histogram snapshot now includes count, min, max, average, p50, and p95.
- Metrics endpoint remains aggregate-only and does not expose raw prompt text, raw tenant ID, or raw PII.

## Verification

```powershell
D:\anaconda\envs\torchtest\python.exe -m pytest ai-service\tests\test_v180_observability_real_signals.py ai-service\tests\test_v180_enterprise_api_java_contract.py
```

Result: `8 passed in 2.14s`

## Boundary

This phase verifies in-process FastAPI metrics. External Prometheus scraping, log shipping, dashboards, alerting, and distributed tracing remain later deployment-readiness work.
