# Agent-RAG Phase 3A Limitations

Phase 3A verifies local real BGE-M3 dense retrieval and FAISS compatibility for
a controlled synthetic benchmark. It does not claim production readiness.

Phase 3A.1 corrected the original evaluation math. Old nDCG values above 1 are
invalid and are retained only as audit history. The corrected benchmark is a
synthetic controlled fixture and is lexically biased; BGE-M3 dense-only did not
beat BM25 on the corrected fixture.

## Not Verified

- Model reranker quality.
- Real LLM answer quality.
- Model fine-tuning.
- Million-scale knowledge base.
- Multi-process FAISS consistency.
- Distributed vector database.
- Production concurrency.
- Production deployment.

## Operational Boundaries

- BGE-M3 remains optional.
- Hash fixture mode remains for fast deterministic tests.
- Generated FAISS indexes remain Git-ignored.
- Local model paths are supplied through environment variables.
- Missing model assets produce explicit `AGENT_RAG_REAL_DENSE_NOT_VERIFIED`.
- Hash fallback is never labeled as real dense retrieval.

## Gate Boundaries

The successful Phase 3A gate means:

- local BGE-M3 loaded
- real embeddings were generated
- FAISS `IndexFlatIP` was built and searched
- model/index compatibility was checked
- fallback behavior was exercised
- synthetic benchmark and E2E passed

It does not mean Enterprise RAG production capability has been proven.

## Phase 3A.2 Dense Quality Boundary

Phase 3A.2 confirms that dense retrieval is numerically healthy and FAISS is
correct, but quality gain is limited to semantic cases in the controlled
fixture.

Still not claimed:

- `BGE-M3 quality verified`
- `Hybrid retrieval improves all retrieval quality`
- `Dense retrieval is production-ready`

The current provider uses generic Transformers CLS pooling:

```text
AutoTokenizer + AutoModel.last_hidden_state[:, 0]
```

That path is stable enough for diagnosis but should not be treated as a final
production embedding wrapper. The default retrieval decision remains
BM25-first, with hybrid-real reserved for deterministic semantic routing.

## Phase 3A.3 Provider Conformance Boundary

Phase 3A.3 implements FlagEmbedding and Sentence Transformers provider paths,
provider fingerprints and provider/index compatibility checks. In the current
environment, both optional packages are unavailable:

```text
PROVIDER_DEPENDENCY_MISSING:FlagEmbedding
PROVIDER_DEPENDENCY_MISSING:sentence-transformers
```

Therefore the system must not claim:

- `AGENT_RAG_OFFICIAL_BGE_M3_PROVIDER_PASS`
- `AGENT_RAG_PHASE3A3_PASS`
- official provider quality improvement

until dependencies are installed and real `dense_vecs` execution is verified.

## Phase 3A.3.1 Offline Dependency Boundary

Phase 3A.3.1 adds audited offline acquisition and verification tooling for
`FlagEmbedding==1.3.5` and `sentence-transformers==3.0.1`.

The current local result is still blocked:

```text
AGENT_RAG_PHASE3A3_WHEELHOUSE_INTEGRITY=BLOCKED
AGENT_RAG_PHASE3A3_OFFLINE_DEPENDENCY=BLOCKED
AGENT_RAG_OFFICIAL_BGE_M3_PROVIDER=BLOCKED
AGENT_RAG_PHASE3A3=BLOCKED
```

The blocked reason is missing offline wheels, not a model quality failure. Phase
3B reranker work remains out of scope until this gate is resolved.

## Phase 3A.3.2 Updated Boundaries

The official FlagEmbedding provider has now been validated in an isolated
offline runtime:

```text
AGENT_RAG_OFFICIAL_BGE_M3_PROVIDER_PASS
AGENT_RAG_PROVIDER_INDEX_FINGERPRINT_PASS
AGENT_RAG_PROVIDER_AB_EVALUATION_PASS
AGENT_RAG_PROVIDER_FALLBACK_PASS
AGENT_RAG_PHASE3A3_PASS
```

What this proves:

- offline wheelhouse installation can reproduce the official provider runtime;
- Torch/CUDA/FAISS were not replaced;
- local BGE-M3 assets can be embedded through `BGEM3FlagModel`;
- generated vectors are 1024-dimensional and normalized;
- matching provider/index fingerprints are enforced;
- fixed benchmark and fallback E2E complete without tenant violations.

What remains not claimed:

- model reranker quality;
- real LLM answer quality;
- model fine-tuning;
- large-scale knowledge base performance;
- production concurrency;
- Enterprise RAG production readiness.

The quality result is parity only:

```text
AGENT_RAG_OFFICIAL_PROVIDER_PARITY_ONLY
```

This is a runtime and governance readiness pass, not a claim that the official
provider improves retrieval quality on every benchmark slice.
