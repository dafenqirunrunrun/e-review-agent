# V2 Enterprise Maturity Baseline

## Scope

This baseline starts the `enterprise-maturity-local-single-node` maturity route
for the internal E-Review Agent repository. The target is a governed local
single-node Agent-RAG runtime with explicit fallback, evidence, tenant
isolation, and audit boundaries. It does not claim production Enterprise RAG.

## Already Verified

- Canonical structured-output contract exists under
  `ai-service/app/contracts/e_review_decision.py`, schema version `v2.0.0`.
- Agent-RAG Phase 1 contract, trace, evidence bundle, rule fallback, and
  idempotency fixture path exist under `ai-service/app/agent_rag/`.
- Phase 2 knowledge governance supports tenant-scoped ingestion, public
  knowledge, document version metadata, active/rollback index semantics, BM25,
  deterministic reranking, hybrid fusion, and no-answer handling.
- Phase 3A introduced local BGE-M3 dense provider abstractions and FAISS index
  compatibility checks.
- Phase 3A.2 selected `bm25-first-semantic-hybrid` as the default retrieval
  mode because dense-only quality did not justify a dense-first default.
- Phase 3A.3.2 validated official FlagEmbedding BGE-M3 with
  `BGEM3FlagModel.encode(...).dense_vecs` in the isolated local validation
  environment and recorded `AGENT_RAG_OFFICIAL_PROVIDER_PARITY_ONLY`.

## Completed But Fixture-Bounded

- The Phase 1 runtime uses deterministic local rules for analysis decisions.
- Hash dense fallback exists for fixture and degraded local execution.
- Deterministic reranker remains the default.
- `AGENT_LLM_PROVIDER=rule` remains the default until real LLM quality and
  safety gates pass.

## Real Model Available

- Official BGE-M3 FlagEmbedding provider is available in the local validation
  evidence from Phase 3A.3.2.
- The selected provider implementation is `flagembedding`.
- Provider conformance is `official-library`.
- The quality conclusion is parity, not quality improvement.

## Real Model Not Yet Verified

- Optional model reranker is not verified.
- Optional local LLM quality is not verified.
- Sentence Transformers remains a reference path, not the selected provider.

## Java Integration State

Existing Java backend modules include AI review, patrol, risk, operation, and
enterprise controller/service code. The Java Agent-RAG business workflow now
has durable run/evidence/override persistence, unified `analyze`, `health`,
`replay`, and `override` API semantics, trusted tenant enforcement, bounded
evidence bundles, replay lineage, append-only human overrides, finite retry,
response validation, and circuit-breaker protection.

The local Java Runtime Acceptance gate passed for:

```text
database migration
AI runtime health
admin-api health
Java HTTP integration
persistence
idempotency
override
replay
circuit breaker open/recovery
```

## Observability State

The local runtime now includes structured logging, request-id trace
correlation, process-local metrics, liveness/readiness endpoints, GPU queue
protection, and FAISS hot-swap locking. These features improve local
demonstration reliability and auditability but do not claim centralized
production observability.

## Frontend State

Existing management frontend already contains AI workbench, review analysis,
Dashboard, risk, operation, and Agent-related experiences. The maturity route
now also contains a dedicated Agent-RAG operations center with overview, run
list, run detail, bounded evidence timeline, fallback/provider display,
append-only human override, replay comparison, and runtime status pages.

The runtime status page now also displays request counters, latency summary,
fallback count, idempotency hits, Provider, Index, and Circuit Breaker status.

## Production Boundary

The project remains a local single-node governed runtime. It does not verify:

```text
HIGH_AVAILABILITY
MILLION_SCALE_KNOWLEDGE
DISTRIBUTED_VECTOR_DATABASE
PRODUCTION_CONCURRENCY
ENTERPRISE_RAG_PRODUCTION_READY
CENTRALIZED_OBSERVABILITY_PLATFORM
DISTRIBUTED_GPU_LOCKING
```

## Current Provider Decision

```text
targetMode=enterprise-maturity-local-single-node
selectedProviderImpl=flagembedding
defaultRetrievalMode=bm25-first-semantic-hybrid
reranker=deterministic
llm=rule
```

FlagEmbedding is selected because it uses the official dense vector encoding
path, has explicit provider semantics, binds fingerprints to the FAISS index,
and is more maintainable than the historical CLS path. It must not be described
as a significant quality improvement over legacy CLS.
