# Agent-RAG Phase 3A.3 Provider Decision

## Quality Conclusion

Current gate conclusion:

```text
AGENT_RAG_OFFICIAL_PROVIDER_QUALITY_BLOCKED
```

This is not one of the final pass conclusions because the official provider
dependency is missing. The project must not claim official BGE-M3 provider
quality until `FlagEmbedding` is installed and `dense_vecs` is actually
generated.

## Selected Provider

Temporary selected provider:

```text
legacy-cls
```

Reason: it is the only real BGE-M3 provider currently executable in this local
environment.

## Default Retrieval Mode

The Phase 3A.2 default remains unchanged:

```text
RAG_DEFAULT_RETRIEVAL_MODE=bm25-first-semantic-hybrid
```

Do not switch the default provider to FlagEmbedding until Phase 3A.3 gate
returns `AGENT_RAG_PHASE3A3_PASS`.

## Fallback

Legacy CLS remains the fallback for historical reproduction. Hash remains the
deterministic fixture fallback. Fallback metadata must expose the actual
effective provider.

## Sentence Transformers

Status:

```text
REFERENCE_PROVIDER_COMPATIBILITY_BLOCKED
```

The reference path is implemented but not executable until the package is
installed.

## Phase 3B Recommendation

Do not enter reranker Phase 3B from this state. First unblock FlagEmbedding or
provide an offline wheelhouse, then rerun Phase 3A.3 gate.

## Phase 3A.3.1 Decision Update

Phase 3A.3.1 adds reproducible offline dependency tooling and validates it
against the cloned `torchtest-phase3a3` environment. The tooling confirms that
the provider dependencies remain missing and that the current wheelhouse is
empty.

Current decision remains unchanged:

```text
selectedProviderImpl=legacy-cls
defaultRetrievalMode=bm25-first-semantic-hybrid
AGENT_RAG_OFFICIAL_PROVIDER_QUALITY_BLOCKED
AGENT_RAG_PHASE3A3_BLOCKED
```

Do not switch the selected provider to `flagembedding` until the dependency
audit, wheelhouse verification, official provider smoke, provider index E2E,
and Phase 3A.3 gate all pass with real `dense_vecs` output.

## Phase 3A.3.2 Decision Update

The official provider gate now passes in the isolated validation environment.

Decision:

```text
selectedProviderImpl=flagembedding
defaultRetrievalMode=bm25-first-semantic-hybrid
qualityConclusion=AGENT_RAG_OFFICIAL_PROVIDER_PARITY_ONLY
AGENT_RAG_PHASE3A3_PASS
```

Rationale:

- FlagEmbedding 1.3.5 executes real `BGEM3FlagModel.encode(...).dense_vecs`.
- The generated FAISS index carries distinct official provider fingerprints.
- Provider/index mismatch scenarios are rejected.
- Phase 3A.2 regression gate remains PASS.
- Full Python regression passed with 470 tests.
- The fixed benchmark shows parity, not improvement; therefore the default
  retrieval mode remains BM25-first hybrid instead of dense-first.

Sentence Transformers remains a reference-only path with
`REFERENCE_PROVIDER_COMPATIBILITY_BLOCKED`; it is not selected as the default.

Phase 3B remains not started in this phase.
