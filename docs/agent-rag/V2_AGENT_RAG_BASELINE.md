# E-Review Agent v2.0 Agent-RAG Governed Runtime Baseline

Status: baseline freeze for the next internal Agent-RAG phase.

This document records the current internal repository state before starting any
v2.0 Agent-RAG implementation work. It is intentionally documentation-only and
does not change runtime code, APIs, database schema, model files, or evaluation
logic.

## Repository Baseline

- Repository: `D:\EReviewAgent\litemall`
- Branch created for this baseline: `experiment/v2.0-agent-rag-governed-runtime`
- Baseline source branch: `experiment/v1.8.2-readiness-blocker-remediation`
- Baseline HEAD: `fe92e59f`
- Public sanitized repository history must not be merged back into this
  internal repository.

## Current Agent Capabilities

The internal project already contains a governed Agent path for ecommerce review
governance. The current implementation includes:

- Bounded Agent orchestration under `ai-service/app/agent/` and
  `ai-service/app/agent_framework/`.
- Tool registry validation for tenant scope, schemas, idempotency, audit
  policy, and bounded execution semantics.
- Human-review routing for fallback, high-risk, prompt-injection, repeated
  schema failure, and unsafe operational cases.
- Agent framework status and analysis APIs under `ai-service/app/api/`.
- Rule and provider-driven execution paths that keep conservative fallback
  behavior available when model runtime is unavailable.

## Current RAG Capabilities

The internal project already contains local Hybrid RAG components:

- Sparse retrieval, dense retrieval, hybrid fusion, reranking hooks, chunking,
  ingestion, evidence verification, tenant ACL filtering, and versioned FAISS
  index support under `ai-service/app/rag/`.
- RAG v2 service and evaluation helpers under `ai-service/app/rag_v2/`.
- Local BGE-M3 and FAISS runtime evidence is documented in the v1.8.x
  enterprise/readiness materials when the corresponding local artifacts are
  present outside Git.
- Rebuildable FAISS binary indexes and model weights remain Git-external.

## Current Benchmark And Evidence

Existing internal evidence describes the following verified or bounded claims:

- v1.7 enterprise engineering gate material under `docs/enterprise/`.
- v1.8.0 difficult multi-tenant RAG benchmark and real retrieval evaluation.
- v1.8.1 independent readiness audit.
- v1.8.2 readiness remediation, including tenant isolation and versioned FAISS
  revalidation notes.
- Public repository gates are separate and do not prove private model or
  internal Agent-RAG production readiness.

Any future v2.0 benchmark must clearly distinguish:

- Project-owned synthetic data.
- Private/local-only evidence.
- Public sanitized evidence.
- Closed holdout or frozen evaluation sets.
- Runtime smoke tests versus formal quality evaluation.

## Tenant Isolation Baseline

Current tenant governance expectations:

- Tenant ID is required in enterprise runtime configuration.
- Retrieval must apply tenant ACL filtering before evidence is used by the
  Agent.
- Logs and metrics must avoid raw tenant IDs and raw user text where possible,
  preferring hashes, trace IDs, aggregate counters, and safe metadata.
- Cross-tenant retrieval leakage remains a hard blocker for any future v2.0
  readiness claim.

## Structured Contract Baseline

The current canonical structured-output contract is:

- Source of truth: `ai-service/app/contracts/e_review_decision.py`
- Schema artifact: `data/contracts/e_review_decision_v2.schema.json`
- Contract version: `v2.0.0`

Runtime, evaluation, and training data should continue to consume this contract
instead of introducing parallel schemas. Raw JSON extraction, contract
normalization, and operational fallback must remain separate so that fallback
outputs do not inflate model-quality metrics.

## Runtime Mode Baseline

The current runtime design keeps multiple modes explicit:

- Rule-based/local fallback mode for stable development and demonstration.
- Optional local model/provider mode when local model weights and dependencies
  are available.
- Governed Agent mode with tool and schema boundaries.
- Hybrid RAG mode when local indexes and retrieval artifacts are present.

Future v2.0 work must keep these modes observable and configurable, and must
not claim production readiness from fallback-only execution.

## Phase 2 Agent-RAG TODO

Recommended next implementation phase:

1. Define a v2.0 Agent-RAG readiness gate that is separate from public preview
   gates.
2. Revalidate BGE-M3 and FAISS artifacts from Git-external local storage.
3. Add a single reproducible Agent-RAG smoke path using tenant-scoped retrieval,
   evidence verification, governed tool calls, and canonical contract output.
4. Add failure tests for empty tenant, cross-tenant evidence, corrupt FAISS
   index, unavailable dense encoder, schema invalid model output, and fallback
   routing.
5. Record latency, schema-valid rate, retrieval hit rate, fallback rate, and
   human-review routing counts without logging private review text.
6. Keep public preview claims separate from internal Agent-RAG readiness claims.

## Non-Goals For This Baseline Commit

- No new Agent tools.
- No new RAG runtime behavior.
- No database migration.
- No API change.
- No model download.
- No training.
- No tag.
- No push requirement.
