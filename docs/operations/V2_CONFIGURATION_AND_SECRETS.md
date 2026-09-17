# E-Review Agent v2.0 Configuration and Secrets

## Purpose

This document defines the local configuration boundary for the v2.0 Agent-RAG release candidate. The project supports local single-node enterprise-maturity verification, but it does not claim production readiness, high availability, or verified real LLM/reranker quality.

## Configuration Boundary

Tracked files may contain:

- Non-secret defaults.
- Localhost ports.
- Placeholder values.
- Test fixtures.
- Documentation examples.

Tracked files must not contain:

- Bearer tokens or session tokens.
- Real API keys.
- Real database passwords.
- Real cloud access keys.
- Real model weight paths tied to a private workstation.
- Customer PII or raw private evidence.

Private local configuration should live outside Git, for example:

```text
%LOCALAPPDATA%\EReviewAgent\
```

Runtime state should live under:

```text
%LOCALAPPDATA%\EReviewAgent\runtime\
```

The runtime home may be overridden with:

```text
E_REVIEW_RUNTIME_HOME
```

## Example Files

Use these tracked examples as templates only:

```text
config/local/.env.agent-rag.example
config/local/application-agent-rag-local.example.yml
```

Copy them to a private local directory before adding real values.

## Local Secret Scan

Run:

```powershell
D:\anaconda\envs\torchtest\python.exe scripts\security\scan_repository_secrets.py
```

Expected token:

```text
E_REVIEW_REPOSITORY_SECRET_SCAN_PASS
```

The scanner intentionally allows documented placeholders and local fixture credentials while flagging high-risk tokens, AWS-style keys, private key blocks, and likely hard-coded API keys in source/config files.

## Remaining Boundaries

```text
REAL_LLM_QUALITY_NOT_VERIFIED
MODEL_RERANKER_NOT_VERIFIED
ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED
NO_PUSH
NO_TAG
NO_RELEASE
```

