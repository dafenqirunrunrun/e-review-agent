# Public Container Risk Exceptions

These exceptions are generated from the real Trivy report for PR #28 run 29657468827. They do not claim production readiness.

Gate boundary: `PRODUCTION_READY_NOT_CLAIMED` remains active. Each exception must be remediated in a dedicated hardening PR or renewed before expiry.

## Summary

- `Java`: 143 unique CRITICAL/HIGH package-CVE exceptions
- `Python`: 7 unique CRITICAL/HIGH package-CVE exceptions
- `e-review-agent-public-admin:v190-phase2 (alpine 3.21.3)`: 37 unique CRITICAL/HIGH package-CVE exceptions
- `e-review-agent-public-backend:v190-phase2 (ubuntu 22.04)`: 3 unique CRITICAL/HIGH package-CVE exceptions
- `e-review-agent-public-customer:v190-phase2 (alpine 3.21.3)`: 37 unique CRITICAL/HIGH package-CVE exceptions
- `litemall-admin/package-lock.json`: 3 unique CRITICAL/HIGH package-CVE exceptions
- `litemall-vue/package-lock.json`: 1 unique CRITICAL/HIGH package-CVE exceptions

## Exception Data

The machine-readable per-CVE allowlist is stored in `docs/security/public_container_risk_exceptions.json`.

Required fields: target, pkgName, vulnerabilityId, severity, installedVersion, fixedVersion, reason, remediation, expires.
