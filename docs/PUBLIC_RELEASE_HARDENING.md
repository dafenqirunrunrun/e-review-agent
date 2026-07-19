# Public Release Hardening

This document records the public-snapshot hardening checks for the sanitized E-Review Agent repository. It is intentionally scoped to the public snapshot and does not describe private datasets, model assets, raw benchmark corpora or internal Git history.

## Scope

- Working directory: `e-review-agent-public-clean`
- Internal source repository: not modified
- Release tag: not created
- Remote publication: completed at `https://github.com/dafenqirunrunrun/e-review-agent`
- Remote verification: completed on draft PR `#27` with GitHub Actions run IDs listed below

## Security Boundary Checks

| Check | Status |
|---|---|
| Forbidden tracked model/index/checkpoint/generated file types | Run locally during hardening |
| Local absolute path and sensitive keyword grep | Run locally during hardening |
| Tracked files larger than 10 MB | Run locally during hardening |
| Local gitleaks | PASS with gitleaks `8.24.3` during publication hardening |
| GitHub gitleaks workflow | PASS: `secret-scan` run `29650925951` |

Ordinary grep scans are supplemental checks only. They are not a replacement for gitleaks.

## Test and Build Boundary

Java tests and Java packaging are reported separately:

- Java tests: `mvn test`
- Java packaging: `mvn -DskipTests package`

The public Python test suite is a reproducible subset of the internal test suite. Private-data, model-asset and internal benchmark dependent tests are excluded from this public repository.

## Current Public Status

| Evidence | Result |
|---|---|
| Python public tests | PASS: GitHub Actions `public-ci` run `29650925931`, job `python-test` |
| Java tests | PASS: GitHub Actions `public-ci` run `29650925931`, job `java-test` |
| Java package | PASS: GitHub Actions `public-ci` run `29650925931`, job `java-test` package step |
| Admin production build | PASS: GitHub Actions `public-ci` run `29650925931`, job `admin-build` |
| Customer production build | PASS: GitHub Actions `public-ci` run `29650925931`, job `customer-build` |
| Repository hygiene | PASS: GitHub Actions `public-ci` run `29650925931`, job `repository-hygiene` |
| Local gitleaks | PASS: gitleaks `8.24.3`, no leaks found |
| GitHub Actions secret scan | PASS: GitHub Actions `secret-scan` run `29650925951`, job `gitleaks` |
| Public Docker runtime | PASS: GitHub Actions `public-runtime-ci` run `29656286535`, job `public-runtime-phase2` |
| Customer-to-Agent E2E smoke | PASS: GitHub Actions `public-runtime-ci` run `29656286535` |
| AI unavailable/recovery smoke | PASS: GitHub Actions `public-runtime-ci` run `29656286535` |
| Public Preview Release Gate | Added for `v1.9.0-public-preview.1`; must pass on `main` before tag and pre-release creation |
| CRITICAL findings | 0 after Phase 4A evidence |
| CRITICAL exceptions | 0 after Phase 4A evidence |
| HIGH exceptions | 55 documented temporary exceptions tracked in issue `#29` |
| Production readiness | Not claimed |

## Preview Release Boundary

The `v1.9.0-public-preview.1` cut is allowed only as a public preview for local demonstration, source-code review and educational evaluation.

Allowed claims:

- `PUBLIC_PREVIEW_RELEASE_ALLOWED`
- `PUBLIC_CRITICAL_VULNERABILITIES_ZERO`
- `PUBLIC_CRITICAL_EXCEPTIONS_ZERO`
- `PUBLIC_RUNTIME_VERIFIED`
- `PUBLIC_BUSINESS_E2E_VERIFIED`
- `PUBLIC_OPERATIONS_BASELINE_VERIFIED`
- `PUBLIC_SECURITY_EXCEPTIONS_PRESENT`
- `PUBLIC_PRODUCTION_RELEASE_BLOCKED`
- `PRODUCTION_READY_NOT_CLAIMED`

Forbidden claims:

- `PRODUCTION_READY`
- `ENTERPRISE_PRODUCTION_READY`
- `PUBLIC_CONTAINER_SECURITY_FULL_PASS`
- `ALL_HIGH_VULNERABILITIES_ZERO`
- `FULL_DISASTER_RECOVERY_VERIFIED`
- `PRIVATE_MODEL_RUNTIME_VERIFIED`
- `ENTERPRISE_RAG_RUNTIME_VERIFIED`

## Latest Local Command Results

```text
python -m pytest -q
Result: PASS, 165 passed

mvn test
Remote result: PASS in GitHub Actions public-ci run 29650925931

mvn -DskipTests package
Result: PASS, Maven BUILD SUCCESS

litemall-admin: npm ci && npm run build:prod
Result: PASS with existing Vue 2 / dependency / bundle-size warnings

litemall-vue: npm ci && npm run build:prod
Result: PASS with existing Vue 2 / dependency / ESLint parser / Sass warnings

gitleaks detect --source . --no-git --redact --exit-code 1
Result: PASS locally with gitleaks 8.24.3; PASS remotely in secret-scan run 29650925951

docker compose -f compose.public.yml config
Result: PASS locally; PASS remotely in public-runtime-ci run 29656286535

docker compose -f compose.public.yml build
Remote result: PASS in public-runtime-ci run 29656286535

docker compose -p <project> -f compose.public.yml up -d
Remote result: PASS in public-runtime-ci run 29656286535

python scripts/ci/wait_for_public_runtime.py
Remote result: PASS in public-runtime-ci run 29656286535

python scripts/ci/public_business_smoke.py
Remote result: PASS in public-runtime-ci run 29656286535

python scripts/ci/public_ai_unavailable_smoke.py
Remote result: PASS in public-runtime-ci run 29656286535

python scripts/readiness/run_public_runtime_phase2_gate.py
Remote result: PASS in public-runtime-ci run 29656286535
```

## Remote CI Evidence

| Workflow | Run ID | Result | Notes |
|---|---:|---|---|
| Public CI | `29650925931` | PASS | `repository-hygiene`, `java-test`, `python-test`, `admin-build` and `customer-build` all succeeded |
| Secret Scan | `29650925951` | PASS | gitleaks workspace scan succeeded |
| Public CI | `29656286537` | PASS | Runtime implementation commit `c97673e`; `repository-hygiene`, `java-test`, `python-test`, `admin-build` and `customer-build` all succeeded |
| Secret Scan | `29656286534` | PASS | Runtime implementation commit `c97673e`; gitleaks workspace scan succeeded |
| Public Runtime CI | `29656286535` | PASS | Compose config/build/up, service health, business E2E, AI unavailable recovery smoke and phase-2 gate all succeeded |

Previous failed publication attempts were remediated by:

- committing frontend `package-lock.json` files and aligning CI Node runtime with the generated lockfile format;
- adding missing Python numeric dependencies required by public tests;
- replacing placeholder secret defaults with empty environment-variable defaults;
- gating private external object-storage tests behind `LITEMALL_RUN_EXTERNAL_STORAGE_TESTS=true`;
- changing one fixed-fixture Java test to skip when the public seed data does not contain that optional product;
- restructuring public audit state hash records to avoid gitleaks false-positive secret-shaped JSON entries.
