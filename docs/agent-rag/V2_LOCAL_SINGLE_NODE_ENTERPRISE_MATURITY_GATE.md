# V2 Local Single-Node Enterprise Maturity Gate

## Purpose

This gate consolidates the local evidence for the v2.0 Agent-RAG governed runtime. It is a local single-node maturity gate, not a production-readiness claim.

## Covered Areas

- Java Agent-RAG persistence, workflow, audit integrity, retention and secure export;
- Python Agent-RAG runtime from Phase 1 through Phase 4;
- security/privacy governance boundaries;
- optional local LLM provider fallback boundaries;
- Admin Operations Center and security governance page buildability.

## Command

```powershell
D:\anaconda\envs\torchtest-phase3a3-tf4\python.exe scripts\readiness\run_agent_rag_v2_local_enterprise_maturity_gate.py
```

## Expected Markers

- `AGENT_RAG_LOCAL_SINGLE_NODE_SECURITY_PASS`
- `AGENT_RAG_LOCAL_SINGLE_NODE_RUNTIME_PASS`
- `AGENT_RAG_LOCAL_SINGLE_NODE_ADMIN_PASS`
- `AGENT_RAG_LOCAL_SINGLE_NODE_TESTS_PASS`
- `AGENT_RAG_V2_LOCAL_ENTERPRISE_MATURITY_PASS`

## Explicit Boundaries

The gate keeps these boundaries visible:

- `REAL_LLM_QUALITY_NOT_VERIFIED`
- `MODEL_RERANKER_NOT_VERIFIED_UNLESS_REAL_ASSET_CONFIGURED`
- `ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED`
- `NO_PUBLIC_REPO_CHANGES`
- `NO_PUSH`
- `NO_TAG`
- `NO_RELEASE`

## Interpretation

PASS means the project is ready for local demonstration and engineering review as an enterprise-oriented Agent-RAG prototype. It does not prove cloud deployment, high availability, distributed locking, SSO, backup/restore, live production monitoring or long-running operations.
