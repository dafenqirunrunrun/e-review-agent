# Agent-RAG Phase 3A.2 Decision

## Answered Questions

Q1. BGE-M3 query/document encoding path correct?

The path is consistent for queries and documents, but it uses generic
Transformers CLS pooling. It is technically stable, not yet a verified
BGE-M3-specific quality path.

Q2. Embedding abnormal/degraded/duplicated?

No numerical abnormality was found. Health checks passed for NaN, Inf, zero
vectors, repeat stability and similarity ordering.

Q3. FAISS metric, normalization and model output match?

Yes. Vectors are normalized and FAISS uses `IndexFlatIP`. Numpy brute-force
inner product and FAISS top-K match.

Q4. Metadata position and FAISS vector position correct?

Yes. Metadata row position, vector position and save/load consistency passed.

Q5. Benchmark too keyword-biased?

Partly yes. The original Phase 3A fixture is lexically biased. Phase 3A.2 adds
semantic, mixed, temporal, tenant and no-answer cases to separate the effects.

Q6. relevantChunkIds too broad/strict?

The labels are synthetic and topic-based. They are adequate for controlled
diagnosis but not a production relevance benchmark.

Q7. Dense better than BM25 on semantic hard cases?

Yes, on the Phase 3A.2 semantic subset: BM25 nDCG@5 is `0.0000`; BGE-M3 and
hybrid nDCG@5 are `0.0428`.

Q8. RRF causing dense to lose influence?

The main issue is not RRF math alone. The current runtime protects sparse top-5,
so dense-only candidates often cannot alter the final top-5.

Q9. Query expansion/filter/dedup hurting dense candidates?

No evidence that expansion replaces the original query. Tenant filtering and
metadata checks passed. Dense candidates remain weak overall.

Q10. Should hybrid default remain on?

No. The evidence supports conditional use only.

## Decision Token

```text
AGENT_RAG_DENSE_SEMANTIC_GAIN_ONLY
```

## Default Mode

Recommended default:

```text
RAG_DEFAULT_RETRIEVAL_MODE=bm25-first-semantic-hybrid
```

This means lexical queries remain BM25-first. Semantic or implicit-intent
queries may use hybrid-real if deterministic routing is enabled and audited.

## Boundaries

Still retained:

```text
MODEL_RERANKER_NOT_VERIFIED
REAL_LLM_QUALITY_NOT_VERIFIED
ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED
NO_PUSH
NO_TAG
NO_RELEASE
```

Phase 3B should wait until this diagnosis is reviewed.

## Phase 3A.3 Follow-up

Phase 3A.2 remains valid as the Legacy CLS dense baseline. Phase 3A.3 adds
official provider conformance work and independent revalidation.

Current Phase 3A.3 status:

```text
AGENT_RAG_OFFICIAL_PROVIDER_QUALITY_BLOCKED
```

The blocker is dependency availability, not a change in Phase 3A.2 metrics:
`FlagEmbedding` and `sentence-transformers` are not installed in the current
environment, and online installation is blocked by TLS/SSL errors. Future
provider decisions should use Phase 3A.3 results after official dense execution
is unblocked.
