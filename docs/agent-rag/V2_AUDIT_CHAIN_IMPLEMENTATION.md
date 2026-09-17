# V2 Audit Chain Implementation

## Purpose

Agent-RAG run evidence must be tamper-evident without storing raw sensitive
inputs. Phase 3C.1 adds hash metadata to run/evidence rows and stores a tenant
scoped chain head.

## Hashes

- `bundleHash`: SHA-256 of bounded evidence JSON.
- `citationSetHash`: SHA-256 of stable citation identity fields.
- `runtimeConfigHash`: SHA-256 of target mode, effective provider/retrieval,
  index, analyzer, schema, and security policy version.
- `effectiveDecisionHash`: SHA-256 of decision source, risk level, action,
  human-review flag, and optional override id.
- `auditHash`: SHA-256 over previous audit hash, tenant id, run id, request id,
  evidence id, citation hash, runtime hash, decision hash, and canonical created
  time.

## Tenant Chain

`litemall_agent_rag_audit_chain` stores the latest audit hash per tenant. The
mapper includes a `for update` selector for transactional chain updates.

## Override Lineage

Override records now support:

- `previousOverrideHash`
- `overrideHash`
- `effectiveDecisionHash`

Overrides do not mutate the original run `auditHash`.

## API

- `GET /admin/agent-rag/runs/{id}/integrity`
- `GET /admin/agent-rag/security/status`

The APIs return hash and status metadata only. They do not return prompts,
model paths, tokens, or raw PII.
