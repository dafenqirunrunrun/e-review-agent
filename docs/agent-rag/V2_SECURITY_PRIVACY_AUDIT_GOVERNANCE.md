# V2 Security, Privacy, and Audit Governance

## Scope

This phase hardens Agent-RAG request handling. It does not add new business
features, production deployment claims, or real LLM quality claims.

## Controls

- PII redaction before retrieval and model analysis.
- Prompt-injection detection before retrieval.
- Manual-review routing for prompt-injection requests.
- Context sanitization for sensitive keys and structured context.
- Hash-only input evidence for audit traceability.
- Secure export helper for redacted operational payloads.
- Runtime security health endpoint:
  `/api/v1/internal/agent-rag/security/health`.

## Evidence

The runtime records:

- `securityGovernanceStatus`
- `piiRedactionCount`
- `promptInjectionDetected`
- `promptInjectionAction`
- `inputContentHash`
- `sanitizedContentHash`

Raw prompt text with detected PII is not persisted in the EvidenceBundle.

## Retention Boundary

The default local audit retention setting is 30 days through:

```text
RAG_AUDIT_RETENTION_DAYS=30
```

This is a local governance setting, not a production retention service.

## Gate

Run:

```powershell
D:\anaconda\envs\torchtest-phase3a3-tf4\python.exe ai-service/scripts/readiness/run_agent_rag_phase3c_security_gate.py
```

Expected tokens:

```text
AGENT_RAG_PII_REDACTION_PASS
AGENT_RAG_PROMPT_INJECTION_GUARD_PASS
AGENT_RAG_AUDIT_HASH_ONLY_PASS
AGENT_RAG_SECURE_EXPORT_PASS
AGENT_RAG_RETENTION_POLICY_PASS
AGENT_RAG_SECURITY_PRIVACY_PASS
```

## Boundaries

```text
REAL_LLM_QUALITY_NOT_VERIFIED
ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED
NO_PUSH
NO_TAG
NO_RELEASE
```
