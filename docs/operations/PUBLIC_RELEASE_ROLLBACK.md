# Public Release Rollback

The public repository does not claim production deployment. Phase 3 verifies backend restart recovery in the public Docker Compose runtime. It does not verify application version rollback.

## Verified Path

1. Start the public runtime.
2. Verify backend readiness.
3. Restart the backend service.
4. Verify backend readiness returns.

The CI script is `scripts/ci/public_rollback_smoke.py`.

The success token is `PUBLIC_BACKEND_RESTART_RECOVERY_PASS`.

Evidence fields include:

- `mode: compose-service-restart`
- `applicationVersionRollback: false`
- `databaseRollback: false`
- `blueGreenRollback: false`

## Not Verified

- Application version rollback.
- Cloud deployment rollback.
- Database migration rollback.
- Blue-green or canary traffic shifting.
- Kubernetes rollout rollback.
