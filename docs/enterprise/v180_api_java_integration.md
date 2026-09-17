# v1.8.0 API and Java Integration

Status: `V180_API_JAVA_INTEGRATION_PASS`

## FastAPI Enterprise Contract

- `GET /api/v1/e-review/health`
- `GET /api/v1/e-review/runtime-status`
- `GET /api/v1/e-review/metrics`
- `POST /api/v1/e-review/analyze`
- `POST /api/v1/e-review/analyze/rag`

Verified behavior:

- Contract version is returned by health and analyze responses.
- Runtime status exposes safe public fields only.
- Analyze responses are idempotent when the same idempotency key is supplied.
- PII redaction count is surfaced and raw PII is not present in the response body.
- Prompt-injection input is detected and routed to human review.
- RAG analyze endpoint sets `rag_enabled=true`.

## Java Admin API Integration

`AiReviewService` now exposes enterprise client methods for health, runtime status, metrics, analyze, and analyze-rag. `AdminAiEnterpriseController` exposes matching admin passthrough endpoints under `/admin/ai/enterprise/*`.

## Verification

Python contract tests:

```powershell
D:\anaconda\envs\torchtest\python.exe -m pytest ai-service\tests\test_v180_enterprise_api_java_contract.py ai-service\tests\test_v170_agent_platform_api.py
```

Result: `14 passed in 2.27s`

Java compile:

```powershell
mvn -pl litemall-admin-api -am -DskipTests package
```

Result: `BUILD SUCCESS`

## Remaining Gate

This phase did not start a separate live FastAPI server and Java process for end-to-end HTTP traffic. Live Java-to-FastAPI HTTP smoke remains a later v1.8 readiness gate.
