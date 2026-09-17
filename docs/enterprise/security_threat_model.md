# Security Threat Model

Primary controls:

- Prompt injection detection downgrades trust and routes to human review.
- PII redaction covers phone numbers, emails, identity-like numbers, cards, tokens, API keys, and cookies.
- Logs keep only trace IDs, hashes, routes, tool names, latency, errors, schema status, and fallback status.
- Tool Registry forbids refunds, bans, compensation, deletion, shipping, or other business writes.
- Closed holdouts and external test data remain guarded by DatasetAccessGuard and isolation checks.

Residual gaps before production:

- No formal compliance certification.
- No enterprise identity provider integration.
- No distributed lock for multi-instance GPU runtime.
