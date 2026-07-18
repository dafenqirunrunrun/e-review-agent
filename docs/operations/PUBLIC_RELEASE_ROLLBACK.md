# Public Release Rollback

The public repository does not claim production deployment. Rollback evidence is limited to the public Docker Compose runtime.

## Verified Path

1. Start the public runtime.
2. Verify backend readiness.
3. Restart the backend service as a rollback/redeploy simulation.
4. Verify backend readiness returns.

The CI script is `scripts/ci/public_rollback_smoke.py`.

## Not Verified

- Cloud deployment rollback.
- Database migration rollback.
- Blue-green or canary traffic shifting.
- Kubernetes rollout rollback.
