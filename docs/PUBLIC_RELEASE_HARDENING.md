# Public Release Hardening

This document records the public-snapshot hardening checks for the sanitized E-Review Agent repository. It is intentionally scoped to the public snapshot and does not describe private datasets, model assets, raw benchmark corpora or internal Git history.

## Scope

- Working directory: `e-review-agent-public-clean`
- Internal source repository: not modified
- Release tag: not created
- Remote publication: pending GitHub account verification and first remote CI run

## Security Boundary Checks

| Check | Status |
|---|---|
| Forbidden tracked model/index/checkpoint/generated file types | Run locally during hardening |
| Local absolute path and sensitive keyword grep | Run locally during hardening |
| Tracked files larger than 10 MB | Run locally during hardening |
| Local gitleaks | `LOCAL_GITLEAKS_NOT_EXECUTED` when the `gitleaks` binary is unavailable |
| GitHub gitleaks workflow | Configured; pending first remote run |

Ordinary grep scans are supplemental checks only. They are not a replacement for gitleaks.

## Test and Build Boundary

Java tests and Java packaging are reported separately:

- Java tests: `mvn test`
- Java packaging: `mvn -DskipTests package`

The public Python test suite is a reproducible subset of the internal test suite. Private-data, model-asset and internal benchmark dependent tests are excluded from this public repository.

## Current Public Status

| Evidence | Result |
|---|---|
| Python public tests | PASS: `164 passed, 1 warning in 3.89s` |
| Java tests | BLOCKED locally: `mvn test` reached Surefire but failed to connect to local MySQL as `litemall`; see `litemall-db/target/surefire-reports/` |
| Java package | PASS: `mvn -DskipTests package` completed with Maven `BUILD SUCCESS` |
| Admin production build | PASS: `npm ci` and `npm run build:prod`; warnings include missing `rmNotice` export and bundle-size warnings |
| Customer production build | PASS: `npm ci` and `npm run build:prod`; warnings include Vue 2/deprecated dependency, ESLint parser and Sass deprecation warnings |
| Local gitleaks | `LOCAL_GITLEAKS_NOT_EXECUTED`; the local `gitleaks` binary was unavailable |
| GitHub Actions | Pending remote publication |
| Docker runtime | Pending verification |
| Production readiness | Not claimed |

## Latest Local Command Results

```text
python -m pytest -ra
Result: PASS, 164 passed, 1 warning

mvn test
Result: BLOCKED locally, MySQL access denied for user 'litemall'@'localhost'

mvn -DskipTests package
Result: PASS, Maven BUILD SUCCESS

litemall-admin: npm ci && npm run build:prod
Result: PASS with existing Vue 2 / dependency / bundle-size warnings

litemall-vue: npm ci && npm run build:prod
Result: PASS with existing Vue 2 / dependency / ESLint parser / Sass warnings
```
