# Public Operations Runbook

## Start

```bash
docker compose -f compose.public.yml build
docker compose -p ereview-public-local -f compose.public.yml up -d
python scripts/ci/wait_for_public_runtime.py
```

The default public preview ports are bound to `127.0.0.1` for local review. Do not expose this Compose runtime directly to the public Internet.

## Smoke

```bash
python scripts/ci/public_business_smoke.py
python scripts/ci/public_observability_smoke.py
python scripts/ci/public_backup_restore_smoke.py
python scripts/ci/public_rollback_smoke.py
```

The backup smoke verifies only `PUBLIC_MYSQL_LOGICAL_PROBE_RESTORE_PASS` for one probe table. The rollback smoke verifies only `PUBLIC_BACKEND_RESTART_RECOVERY_PASS` for Docker Compose backend restart recovery.

## Gate

```bash
python scripts/readiness/run_public_ops_phase3_gate.py
```

## Stop

```bash
docker compose -p ereview-public-local -f compose.public.yml down -v --remove-orphans
```

## Boundaries

This runbook verifies a public demo runtime only. Production deployment, full database disaster recovery, application version rollback, private model runtime and Enterprise RAG runtime remain outside this public readiness claim.

`v1.9.0-public-preview.1` may claim public preview verification after the preview release gate passes. It must continue to state `PUBLIC_PRODUCTION_RELEASE_BLOCKED` and `PRODUCTION_READY_NOT_CLAIMED` while HIGH security exceptions remain.
