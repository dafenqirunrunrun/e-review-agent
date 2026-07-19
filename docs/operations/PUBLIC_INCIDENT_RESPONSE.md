# Public Incident Response

## Triage

1. Check GitHub Actions job status.
2. Download the operations evidence artifact.
3. Inspect `business-smoke-summary.json`, `observability-smoke-summary.json`, `backup-restore-smoke-summary.json` and `rollback-smoke-summary.json`.
4. Check container logs collected by the failing workflow.

## Severity

- P0: public runtime cannot start.
- P1: review governance E2E fails.
- P2: observability, MySQL logical probe restore, SBOM or backend restart recovery evidence is incomplete.
- P3: documentation mismatch or non-blocking workflow annotation.

## Data Handling

Do not paste tokens, passwords, full user review text or private paths into issues.
