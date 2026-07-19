# Public Observability

The public runtime supports request correlation with `X-Request-ID`.

Request IDs must match `^[A-Za-z0-9._:-]{1,128}$`. Missing, blank, overlong or unsafe values are replaced with a generated UUID. Valid IDs are preserved across the Java backend and AI service boundary.

## Backend

- Every HTTP response includes `X-Request-ID`.
- If a client does not send one, the backend creates one.
- Unsafe client-provided values, including control characters or CRLF-like values, are not reused.
- Java logs include `service`, `request_id`, `operation`, `status` and `duration_ms`.
- `/public/runtime/metrics` exposes non-sensitive counters for HTTP requests, AI calls, Agent scans, stored analyses and risk tasks.

## AI Service

- Every HTTP response includes `X-Request-ID`.
- Unsafe client-provided values are replaced before being returned.
- `/metrics` exposes non-sensitive public counters.
- `/api/v1/review/analyze` increments AI analysis success/failure counters.

## Sensitive Data Boundary

Logs and metrics must not include passwords, tokens, full review text, model prompts or private image paths.
