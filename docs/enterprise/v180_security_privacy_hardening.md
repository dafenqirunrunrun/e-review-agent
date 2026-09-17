# v1.8.0 Security and Privacy Hardening

Status: `V180_SECURITY_PRIVACY_HARDENING_PASS`

## Implemented Controls

- Prompt-injection detection now covers additional English attacks: system/developer prompt disclosure, safety bypass, business-write manipulation, and review deletion requests.
- Prompt-injection detection now covers Chinese attacks that ask the system to ignore instructions, reveal prompts, delete reviews, clear records, or alter database content.
- PII/secret redaction now covers phone, email, ID number, payment-card-like values, `api_key`/`token`/`cookie`, Bearer tokens, and JWT-like values.
- Safe structured logging remains allowlist-only and drops raw review text, token, cookie, and password fields.
- Enterprise API response checks verify that sensitive values are redacted and injection is routed to human review.

## Verification

```powershell
D:\anaconda\envs\torchtest\python.exe -m pytest ai-service\tests\test_v180_security_privacy_hardening.py ai-service\tests\test_v180_enterprise_api_java_contract.py
```

Result: `13 passed in 2.34s`

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-security-hygiene-check.ps1
```

Result: `SECURITY_HYGIENE_CHECK_PASS`, scanned files: `1006`

## Boundary

This phase hardens local static/runtime checks. It does not claim formal penetration testing, external audit, or production certification.
