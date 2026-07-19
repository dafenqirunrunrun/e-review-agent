# E-Review Agent

Enterprise-oriented e-commerce review governance system with AI analysis, Agent inspection, risk workflows and auditable readiness boundaries.

![Java](https://img.shields.io/badge/Java-Spring%20Boot-blue)
![Vue 2](https://img.shields.io/badge/Vue-2.x-42b883)
![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688)
![MySQL](https://img.shields.io/badge/MySQL-8.x-4479A1)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-public%20preview-orange)

## Public Preview Status

| Gate | Status |
|---|---|
| Public Preview | Verified |
| Public CI | PASS |
| Docker Runtime | PASS |
| Business E2E | PASS |
| CRITICAL Findings | 0 |
| Known HIGH Exceptions | 55 |
| Production Deployment | Not recommended |
| Production Readiness | Not claimed |
| Private Model Runtime | Not included |
| Enterprise RAG Runtime | Not included |

Security notice: this public preview contains documented temporary HIGH-severity dependency exceptions. It is intended for local demonstration, source-code review and educational evaluation. Do not expose the default Docker Compose runtime directly to the public Internet.

## Overview

E-Review Agent extends the open-source [linlinjava/litemall](https://github.com/linlinjava/litemall) project into a review-governance prototype for graduation-project, engineering-practice and portfolio demonstration.

The public preview core loop is:

1. A customer browses products in the H5 storefront.
2. The customer submits an order through a demo payment and demo shipping flow.
3. The customer confirms receipt and publishes a text/image review.
4. The backend stores the review in the original litemall comment table.
5. The inspection Agent scans unprocessed comments.
6. The AI service returns structured review analysis.
7. High-risk results generate risk tasks.
8. Operators handle tasks in the admin console.
9. Dashboard metrics update from persisted records.

Payment, logistics and refund integrations are demo-mode implementations. This repository does not claim production readiness.

## Highlights

| Area | What it demonstrates |
|---|---|
| Customer-to-Agent loop | End-to-end review governance from H5 customer review to admin operation workflow |
| Agent inspection | Manual or scheduled scanning of unprocessed comments |
| Structured AI analysis | JSON-contract based sentiment, risk level, risk type and operation suggestion output |
| Risk workflow | Risk task creation, detail view, status transition and operation log |
| Public audit boundary | Sanitized source snapshot without model weights, private data, raw benchmark assets or internal Git history |

## Business Flow

```mermaid
flowchart LR
    A["Customer browses product"] --> B["Submit demo order"]
    B --> C["Demo payment and shipping"]
    C --> D["Confirm receipt"]
    D --> E["Publish text/image review"]
    E --> F["Agent inspection"]
    F --> G["Structured AI analysis"]
    G --> H{"High risk?"}
    H -- "No" --> I["Persist analysis"]
    H -- "Yes" --> J["Create risk task"]
    J --> K["Operator handles task"]
    K --> L["Dashboard updates"]
```

## Architecture

```mermaid
flowchart TB
    U["Customer H5<br/>Vue 2 + Vant"]
    A["Admin Console<br/>Vue 2 + Element UI"]
    B["Spring Boot Backend"]
    AI["FastAPI AI Service"]
    DB[("MySQL")]
    AG["Review Inspection Agent"]
    RAG["Optional RAG / local model experiments"]

    U --> B
    A --> B
    B --> DB
    AG --> B
    B --> AI
    AI --> RAG
    AI --> B
```

## Tech Stack

| Layer | Stack |
|---|---|
| Backend | Java, Spring Boot, Maven, MyBatis |
| Admin frontend | Vue 2, Element UI, Axios |
| Customer H5 | Vue 2, Vant 2, Vuex, Vue Router |
| AI service | Python, FastAPI, Pydantic, pytest |
| Data | MySQL |
| Optional experiments | Local model adapters, VLM provider wiring, BGE-M3/FAISS retrieval code paths |

## Repository Structure

```text
e-review-agent/
|-- ai-service/          # FastAPI AI service and public tests
|-- data/                # Public schemas and governance metadata
|-- litemall-admin/      # Vue 2 admin console
|-- litemall-vue/        # Vue 2 + Vant customer H5 frontend
|-- litemall-admin-api/  # Spring Boot admin API
|-- litemall-wx-api/     # Spring Boot customer API
|-- litemall-db/         # Database schema, mappers and AI SQL migrations
|-- litemall-core/       # Shared Java configuration and infrastructure
|-- litemall-all/        # Combined Spring Boot entry
|-- docs/                # Public project documentation
`-- compose.public.yml   # Public Docker Compose runtime used by CI
```

## Quick Start

### Requirements

- JDK 8+
- Maven 3.6+
- MySQL 5.7 or 8.x
- Node.js compatible with Vue CLI 3/4 projects
- Python 3.10+

### Database

```bash
mysql -u root -p
CREATE DATABASE litemall DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Import schema and AI migration SQL files from `litemall-db/sql/` as needed. This public snapshot does not include production database backups.

### Java Backend

```bash
mvn test
mvn -DskipTests package
```

Typical local service ports:

- wx-api: `http://localhost:8080`
- admin-api: `http://localhost:8083`

### AI Service

```bash
cd ai-service
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
python -m pytest -ra
uvicorn app.main:app --host 0.0.0.0 --port 8008
```

### Admin Console

```bash
cd litemall-admin
npm ci
npm run build:prod
npm run dev
```

### Customer H5

```bash
cd litemall-vue
npm ci
npm run build:prod
npm run dev
```

## Public Test Scope

The public snapshot includes a reproducible subset of the internal test suite. Private-data, model-asset and internal benchmark dependent tests are excluded from this repository.

| Evidence | Current public status |
|---|---|
| Public Python test suite | PASS in GitHub Actions `public-ci` run `29650925931` |
| Java unit tests | PASS in GitHub Actions `public-ci` run `29650925931` |
| Java packaging | PASS in GitHub Actions `public-ci` run `29650925931` |
| Admin production build | PASS in GitHub Actions `public-ci` run `29650925931` |
| Customer production build | PASS in GitHub Actions `public-ci` run `29650925931` |
| Local gitleaks scan | PASS locally with gitleaks `8.24.3` during publication hardening |
| GitHub gitleaks workflow | PASS in GitHub Actions `secret-scan` run `29650925951` |
| Public Docker runtime | PASS in GitHub Actions `public-runtime-ci` run `29656286535` |
| Customer-to-Agent E2E smoke | PASS in GitHub Actions `public-runtime-ci` run `29656286535` |
| AI unavailable/recovery smoke | PASS in GitHub Actions `public-runtime-ci` run `29656286535` |
| Public observability smoke | Phase 3 evidence validates request correlation and metrics |
| Public MySQL logical probe restore | Phase 3 verifies a single probe-table restore only |
| Public backend restart recovery | Phase 3 verifies compose service restart recovery only |
| Public container risk baseline | CRITICAL findings are zero; 55 documented temporary HIGH exceptions remain |
| Public preview release gate | Validates runtime, business E2E, operations evidence, SBOM and security evidence |
| Production readiness | Not claimed |

## AI Capability Boundaries

- Rule/mock mode is sufficient for the core business demo and does not require model weights.
- Local text-model, VLM and RAG paths are experimental and optional.
- Model weights, adapters, checkpoints, FAISS indexes and private datasets are intentionally excluded.
- AI output is decision support. Important operational decisions should still keep human review.

## Docker Compose

Public Docker runtime verification is implemented in `compose.public.yml` and `.github/workflows/public-runtime-ci.yml`.

```bash
docker compose -f compose.public.yml config
docker compose -f compose.public.yml build
docker compose -p ereview-public-local -f compose.public.yml up -d
PUBLIC_COMPOSE_PROJECT=ereview-public-local python scripts/ci/wait_for_public_runtime.py
python scripts/ci/public_business_smoke.py
PUBLIC_COMPOSE_PROJECT=ereview-public-local python scripts/ci/public_ai_unavailable_smoke.py
docker compose -p ereview-public-local -f compose.public.yml down -v --remove-orphans
```

Public Docker verification uses a deterministic public rule engine so the business workflow can be reproduced without private model assets. This mode does not represent the private local-model or Enterprise RAG runtime.

The public Compose file binds exposed preview ports to `127.0.0.1` by default. It is a local-preview runtime and must not be published directly to the public Internet.

Remote runtime implementation verification:

- Public Runtime CI: PASS, run `29656286535`, job `public-runtime-phase2`.
- Public CI: PASS, run `29656286537`, jobs `repository-hygiene`, `java-test`, `python-test`, `admin-build`, `customer-build`.
- Secret Scan: PASS, run `29656286534`, job `gitleaks`.
- Draft PR: [#27](https://github.com/dafenqirunrunrun/e-review-agent/pull/27).

Public operations Phase 3 evidence is tracked in draft PR [#28](https://github.com/dafenqirunrunrun/e-review-agent/pull/28). The current Phase 3 status is intentionally partial: legacy CRITICAL/HIGH dependency exceptions are visible and tracked, so `PUBLIC_RELEASE_SECURITY_BLOCKED` and `PRODUCTION_READY_NOT_CLAIMED` remain active.

Runtime docs:

- [Public Runtime Audit](docs/runtime/PUBLIC_RUNTIME_AUDIT.md)
- [Public Docker Runbook](docs/runtime/PUBLIC_DOCKER_RUNBOOK.md)
- [Public Business E2E](docs/runtime/PUBLIC_BUSINESS_E2E.md)
- [Public Runtime Limitations](docs/runtime/PUBLIC_RUNTIME_LIMITATIONS.md)

Operations and security docs:

- [Public Operations Phase 3 Audit](docs/operations/PUBLIC_PHASE3_AUDIT.md)
- [Public Backup And Restore](docs/operations/PUBLIC_BACKUP_RESTORE.md)
- [Public Release Rollback](docs/operations/PUBLIC_RELEASE_ROLLBACK.md)
- [Public Observability](docs/observability/PUBLIC_OBSERVABILITY.md)
- [Public Container Security](docs/security/PUBLIC_CONTAINER_SECURITY.md)
- [Public Container Risk Exceptions](docs/security/PUBLIC_CONTAINER_RISK_EXCEPTIONS.md)

## Open Source Scope

This is a sanitized public snapshot. It excludes:

- internal Git history;
- model weights, adapters and checkpoints;
- private datasets and raw training data;
- full benchmark corpora;
- real user data and database backups;
- FAISS or other large index binaries;
- detailed soak raw logs;
- screenshots containing personal information, secrets or local paths.

See [docs/OPEN_SOURCE_SCOPE.md](docs/OPEN_SOURCE_SCOPE.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Security

Do not publish passwords, tokens, cookies, database dumps, private keys, real user data or screenshots containing sensitive information. See [SECURITY.md](SECURITY.md).

## License

This snapshot retains the upstream litemall MIT license boundary and adds E-Review Agent project files under the repository license. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
