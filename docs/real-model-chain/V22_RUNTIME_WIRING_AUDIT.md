# v2.2 Runtime Wiring Audit

## Purpose

This audit separates standalone smoke scripts from the formal Agent-RAG runtime
path. Smoke results prove that a model can load and execute. Runtime wiring
proves that normal analyze requests use the configured provider and preserve
sanitized evidence metadata.

## Reranker Wiring

| Layer | Status |
| --- | --- |
| Standalone smoke | `AGENT_RAG_V22_REAL_RERANKER_RUNTIME_PASS` |
| Formal provider | `LocalModelReranker` now resolves v2.2 assets from `AGENT_RAG_V22_ASSET_MANIFEST`. |
| Official implementation | `FlagEmbedding.FlagReranker` via provider implementation `flagembedding`. |
| Runtime path | `AgentRagRuntime -> GovernedReranker -> LocalModelReranker -> FlagReranker.compute_score`. |
| Fallback behavior | Deterministic fallback remains available unless `RAG_REAL_RERANKER_REQUIRED=true`. |
| Runtime marker | `real_reranker_runtime` passed through `AgentRagRuntime`. |

Normal runtime evidence must show:

```text
requestedRerankerType = local-model
effectiveRerankerType = local-model
rerankerFallbackUsed = false
rerankerInputCount > 0
rerankerOutputCount > 0
rerankerModelId = BAAI/bge-reranker-v2-m3
rerankerRevision = 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e
```

## Dense Retrieval Wiring

| Layer | Status |
| --- | --- |
| Standalone real dense marker | Phase3A real BGE-M3 tests pass when model env is supplied. |
| Formal runtime hook | `AgentRagRuntime` can route retrieval through `GovernedHybridRuntime` when `RAG_DEFAULT_RETRIEVAL_MODE` is `real-dense` or `hybrid-real`. |
| FAISS path | `GovernedHybridRuntime -> BgeM3FaissDenseRetriever -> BGE-M3 provider -> FaissVectorIndex`. |
| Evidence | `RetrievalTrace` and `AgentRagEvidenceBundle` preserve dense provider, effective retrieval mode, FAISS metadata and dense fallback reason. |
| Default behavior | Existing BM25-first behavior remains unchanged unless the retrieval mode is configured. |

Normal runtime evidence must show:

```text
requestedRetrievalMode = hybrid-real or real-dense
effectiveRetrievalMode = hybrid-real or real-dense
denseProvider = bge-m3 / bge-m3-legacy-cls / hash fixture in tests
faissIndexType = IndexFlatIP
denseFallbackUsed = false for required real dense mode
```

## LLM Wiring

| Layer | Status |
| --- | --- |
| Standalone smoke | `AGENT_RAG_V22_REAL_LLM_RUNTIME_PASS` |
| Formal provider | `LocalQwenTransformersProvider` resolves the v2.2 LLM asset from `AGENT_RAG_V22_ASSET_MANIFEST` or explicit `AGENT_LLM_*` aliases. |
| Official implementation | Transformers `AutoModelForCausalLM.generate` using the local Qwen3 model. |
| Runtime path | `AgentRagRuntime -> AgentRagLlmDecider -> LocalQwenTransformersProvider -> LocalQwenRuntime -> generate`. |
| Fallback behavior | Governed rule fallback remains available for unavailable model, invalid JSON, invalid citation or ungrounded output. |
| Runtime marker | `real_llm_runtime` passed through `AgentRagRuntime`. |

Normal runtime evidence must show:

```text
requestedAnalysisProvider = local_qwen3_transformers
effectiveAnalysisProvider = local_qwen3_transformers
llmFallbackUsed = false
llmModelId = Qwen/Qwen3-1.7B
llmRevision = 70d244cc86ccca08cf5af4e1e306ecf908b1ad5e
llmInputTokens > 0
llmOutputTokens > 0
structuredOutputValid = true
groundingStatus = GROUNDED or ABSTAINED
```

## Boundary

This audit does not close the full quality blockers. The following remain until
runtime marker tests, frozen benchmarks, Java E2E and soak all pass:

```text
MODEL_RERANKER_NOT_VERIFIED
REAL_LLM_QUALITY_NOT_VERIFIED
```

## Java and Admin Evidence Pass-Through

The Java admin API now accepts and preserves the v2.2 real-model metadata emitted
by the Python runtime:

- `AgentRagRetrievalResult` accepts dense retrieval and reranker metadata,
  including effective retrieval mode, FAISS metadata, reranker model ID,
  revision, fingerprint, duration and fallback state.
- `AgentRagRuntime` accepts local Qwen3 analysis metadata, including requested
  and effective analysis provider, model ID, revision, fingerprint, prompt
  version, prompt fingerprint, token counts, structured output validity,
  grounding status, abstention and fallback state.
- `AgentRagWorkflowService` persists the lightweight provider, retrieval,
  fallback and human-review fields already supported by the existing run table.
  No model path, full prompt or raw model output is persisted.
- The Admin detail page reads the bounded evidence bundle and displays sanitized
  retrieval, rerank and LLM evidence. The runtime page displays GPU residency
  counters when the Python health endpoint supplies them.

Targeted Java validation:

```text
mvn -pl litemall-admin-api -am "-Dtest=AgentRagClientContractTest,AgentRagWorkflowPersistenceTest" -DfailIfNoTests=false test
Tests run: 16, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```
