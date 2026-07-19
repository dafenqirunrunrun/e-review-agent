# Public Container Risk Exceptions

These exceptions are generated from the real Trivy report for PR #28 run 29657468827. They do not claim production readiness.

Gate boundary: `PRODUCTION_READY_NOT_CLAIMED` remains active. Each exception must be remediated in a dedicated hardening PR or renewed before expiry.

The public baseline contains documented temporary CRITICAL/HIGH exceptions. The exception list makes legacy risk visible and auditable; it does not make the runtime secure or production-ready.

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

Required fields: `target`, `pkgName`, `vulnerabilityId`, `severity`, `installedVersion`, `fixedVersion`, `reason`, `remediation`, `owner`, `trackingIssue`, `createdAt`, `expires`, `disposition` and `reachability`.

Each exception is scoped by at least target, package name, vulnerability ID, severity and installed version. A package upgrade, severity change or target change must create a new review instead of silently matching an old exception.

Current disposition values are temporary risk acceptance records, tracked by [issue #29](https://github.com/dafenqirunrunrun/e-review-agent/issues/29). `reachability: unknown` is treated as visible residual risk, not as proof that the finding is safe.
