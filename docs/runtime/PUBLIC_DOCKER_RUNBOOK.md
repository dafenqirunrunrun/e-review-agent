# Public Docker Runbook

This runbook covers the public, reproducible Docker runtime only.

## Build

```bash
docker compose -f compose.public.yml config
docker compose -f compose.public.yml build
```

## Start

```bash
docker compose -p ereview-public-local -f compose.public.yml up -d
```

## Wait For Health

```bash
PUBLIC_COMPOSE_PROJECT=ereview-public-local python scripts/ci/wait_for_public_runtime.py
```

The wait script checks:

- MySQL ping
- AI liveness
- AI readiness
- Backend readiness
- Admin page
- Customer page

## Run Business Smoke

```bash
python scripts/ci/public_business_smoke.py
```

## Run AI Unavailable Smoke

```bash
PUBLIC_COMPOSE_PROJECT=ereview-public-local python scripts/ci/public_ai_unavailable_smoke.py
```

## Run Gate

```bash
python scripts/readiness/run_public_runtime_phase2_gate.py
```

## Cleanup

```bash
docker compose -p ereview-public-local -f compose.public.yml down -v --remove-orphans
```

## Public Ports

- Backend: `http://localhost:8080`
- AI service: `http://localhost:8008`
- Admin frontend: `http://localhost:8081`
- Customer H5 frontend: `http://localhost:8082`

## Public Test Accounts

These are local CI/demo credentials only:

- Admin: `ci_public_admin` / `public_ci_admin_123`
- Customer: `ci_public_user` / `public_ci_user_123`

Do not reuse these credentials in production.
