# Public Operations Runbook

## Start

```bash
docker compose -f compose.public.yml build
docker compose -p ereview-public-local -f compose.public.yml up -d
python scripts/ci/wait_for_public_runtime.py
```

## Smoke

```bash
python scripts/ci/public_business_smoke.py
python scripts/ci/public_observability_smoke.py
python scripts/ci/public_backup_restore_smoke.py
python scripts/ci/public_rollback_smoke.py
```

## Gate

```bash
python scripts/readiness/run_public_ops_phase3_gate.py
```

## Stop

```bash
docker compose -p ereview-public-local -f compose.public.yml down -v --remove-orphans
```

## Boundaries

This runbook verifies a public demo runtime only. Production deployment, private model runtime and Enterprise RAG runtime remain outside this public readiness claim.
