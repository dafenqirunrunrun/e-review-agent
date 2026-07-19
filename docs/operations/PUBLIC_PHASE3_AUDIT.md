# Public Operations Phase 3 Audit

Phase 3 adds verifiable public operations evidence for the sanitized E-Review Agent repository. It does not claim production readiness.

## Scope

- Observability: request correlation, public metrics and runtime smoke.
- Recovery: public MySQL logical probe-table restore smoke.
- Security: Trivy filesystem and container image scans with scoped, expiring CRITICAL/HIGH exception records.
- SBOM: SPDX JSON SBOM artifacts for public runtime images.
- Release safety: public compose backend restart recovery smoke.
- Runbooks: operator-facing public documentation.

## Boundaries

- PRODUCTION_READY_NOT_CLAIMED.
- PRIVATE_MODEL_RUNTIME_NOT_VERIFIED.
- ENTERPRISE_RAG_RUNTIME_NOT_VERIFIED.
- No Kubernetes, cloud production deployment, HA MySQL, queue middleware, new model, new RAG, new training, tag or release is introduced.
- Full database disaster recovery, application version rollback, database rollback and blue-green rollback are not verified in this phase.

## Current Status

- `PUBLIC_OBSERVABILITY_PASS`
- `PUBLIC_MYSQL_LOGICAL_PROBE_RESTORE_PASS`
- `PUBLIC_BACKEND_RESTART_RECOVERY_PASS`
- `PUBLIC_SBOM_PASS`
- `PUBLIC_CONTAINER_RISK_BASELINE_AUDITED`
- `PUBLIC_CONTAINER_EXCEPTIONS_VALIDATED`
- `PUBLIC_RELEASE_SECURITY_BLOCKED`
- `PUBLIC_OPERATIONS_PHASE3_PARTIAL`

## Evidence

CI artifacts are produced under `artifacts/` during GitHub Actions runs. Only lightweight templates are tracked in the repository.
