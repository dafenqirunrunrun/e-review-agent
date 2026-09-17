# V2 Phase 3C.1 End-to-End Security Gap Analysis

## Baseline

- Repository: `D:\EReviewAgent\litemall`
- Branch: `experiment/v2.0-agent-rag-governed-runtime`
- Starting HEAD: `33bb27cb`

## Coverage Matrix

| Area | Status Before 3C.1 | 3C.1 Action |
| --- | --- | --- |
| Python request pre-governance | Completed | Reused `AgentRagSecurityGovernor` |
| Python Evidence governance | Completed | Reused hash-only evidence fields |
| Java persistence security fields | Missing | Added run/evidence/override fields and SQL migration |
| Database audit chain | Missing | Added `litemall_agent_rag_audit_chain` |
| Retention actual task | Missing | Planned for next module |
| Secure Export Java API | Missing | Planned for next module |
| Export independent permission | Missing | Planned for next module |
| Admin security display | Partial | Added backend security status/integrity API first |
| Security Runtime E2E | Partial | Python gate exists; Java E2E planned after API wiring |

## Findings

- Java workflow already persists bounded evidence and `bundleHash`.
- Java workflow did not persist PII, prompt-injection, or audit-integrity fields.
- Override history was append-only, but did not yet include override hash lineage.
- Replay creates a new run, but lineage fields still need final API display
  hardening.
- Admin detail page displays evidence hash, but security/integrity blocks need a
  follow-up UI module.

## Decision

Phase 3C.1 is split into two commits:

1. Durable audit integrity: migration, Java DTO/domain/mapper fields, audit
   hash service, integrity/status APIs, tests, and docs.
2. Retention and secure export: Java retention service/API, export API,
   independent permission, Admin UI, E2E, and gate.
