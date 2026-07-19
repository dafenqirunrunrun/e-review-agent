# Public Container Risk Exceptions

These exceptions are generated from the public Trivy baseline and are tracked under issue #29. They do not claim production readiness.

Gate boundary: `PRODUCTION_READY_NOT_CLAIMED` remains active. Each exception must be remediated in a dedicated hardening PR or renewed before expiry.

After Phase 4A, CRITICAL exceptions are not allowed. The remaining exception list tracks temporary HIGH findings only. The exception list makes legacy risk visible and auditable; it does not make the runtime secure or production-ready.

## Summary

- CRITICAL exceptions: 0
- HIGH exceptions retained for Phase 4B: 196
- Tracking issue: [#29](https://github.com/dafenqirunrunrun/e-review-agent/issues/29)

## Exception Data

The machine-readable per-CVE allowlist is stored in `docs/security/public_container_risk_exceptions.json`.

Required fields: `target`, `pkgName`, `vulnerabilityId`, `severity`, `installedVersion`, `fixedVersion`, `reason`, `remediation`, `owner`, `trackingIssue`, `createdAt`, `expires`, `disposition` and `reachability`.

Each exception is scoped by at least target, package name, vulnerability ID, severity and installed version. A package upgrade, severity change or target change must create a new review instead of silently matching an old exception.

Current disposition values are temporary HIGH risk acceptance records, tracked by [issue #29](https://github.com/dafenqirunrunrun/e-review-agent/issues/29). `reachability: unknown` is treated as visible residual risk, not as proof that the finding is safe.
