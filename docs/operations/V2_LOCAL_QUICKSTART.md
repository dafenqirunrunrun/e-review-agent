# E-Review Agent v2.0 Local Quickstart

## Scope

This guide starts the local single-node Agent-RAG release candidate. It is intended for reproducible demo and verification, not production deployment.

## Prepare Private Configuration

Copy the example environment file to a private location:

```powershell
New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\EReviewAgent" | Out-Null
Copy-Item config\local\.env.agent-rag.example "$env:LOCALAPPDATA\EReviewAgent\.env.agent-rag"
```

Fill local-only values in the copied file if needed. Do not commit populated configuration files.

## Build Java Jars

```powershell
mvn -DskipTests package
```

## Doctor

```powershell
powershell -ExecutionPolicy Bypass -File scripts\local\e-review-doctor.ps1 -Python D:\anaconda\envs\torchtest\python.exe
```

Expected token:

```text
E_REVIEW_LOCAL_DOCTOR_PASS
```

Warnings for unconfigured real LLM or model reranker are expected unless those optional assets are configured locally.

## Start

```powershell
powershell -ExecutionPolicy Bypass -File scripts\local\e-review-start.ps1 -Python D:\anaconda\envs\torchtest\python.exe -KeepExisting
```

Default services:

| Service | URL |
| --- | --- |
| AI runtime | `http://127.0.0.1:8008` |
| Admin API | `http://127.0.0.1:8083` |
| Admin UI | `http://127.0.0.1:9527` |

Runtime logs and PID files are written under:

```text
%LOCALAPPDATA%\EReviewAgent\runtime\
```

## Status

```powershell
powershell -ExecutionPolicy Bypass -File scripts\local\e-review-status.ps1
```

Expected token:

```text
E_REVIEW_LOCAL_STATUS_PASS
```

## Smoke

```powershell
powershell -ExecutionPolicy Bypass -File scripts\local\e-review-smoke.ps1
```

Expected token:

```text
E_REVIEW_LOCAL_SMOKE_PASS
```

## Stop

```powershell
powershell -ExecutionPolicy Bypass -File scripts\local\e-review-stop.ps1 -All
```

Expected token:

```text
E_REVIEW_LOCAL_STOP_PASS
```

The stop script only stops processes recorded in the runtime PID directory. It does not kill all Java, Python, or Node processes.

## Boundaries

```text
REAL_LLM_QUALITY_NOT_VERIFIED
MODEL_RERANKER_NOT_VERIFIED
ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED
NO_PUSH
NO_TAG
NO_RELEASE
```

