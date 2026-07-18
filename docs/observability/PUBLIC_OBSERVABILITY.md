# Public Observability

The public runtime supports request correlation with `X-Request-ID`.

## Backend

- Every HTTP response includes `X-Request-ID`.
- If a client does not send one, the backend creates one.
- Java logs include `service`, `request_id`, `operation`, `status` and `duration_ms`.
- `/public/runtime/metrics` exposes non-sensitive counters for HTTP requests, AI calls, Agent scans, stored analyses and risk tasks.

## AI Service

- Every HTTP response includes `X-Request-ID`.
- `/metrics` exposes non-sensitive public counters.
- `/api/v1/review/analyze` increments AI analysis success/failure counters.

## Sensitive Data Boundary

Logs and metrics must not include passwords, tokens, full review text, model prompts or private image paths.
