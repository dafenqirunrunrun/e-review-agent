# V2 Reranker Architecture

## Components

- `GovernedReranker`: selects the requested reranker, applies concurrency
  limits, captures fallback reasons, and returns auditable results.
- `DeterministicGovernedReranker`: stable lexical/fusion fallback used by
  default.
- `LocalModelReranker`: optional local model provider for `FlagEmbedding` or
  `sentence-transformers` assets.
- `RerankerAssetAudit`: sanitized model-file audit without absolute paths.

## Governance Rules

- Tenant scope is validated before reranking.
- Deleted or inactive candidates are rejected.
- Duplicate candidates are rejected.
- NaN and infinite scores are rejected.
- Model failure falls back to deterministic reranking unless
  `RAG_REAL_RERANKER_REQUIRED=true`.
- The runtime records requested/effective reranker type, model fingerprint,
  input/output counts, duration, fallback flag, and fallback reason.

## Evidence Fields

The following fields are included in `RetrievalTrace` and
`AgentRagEvidenceBundle`:

- `requestedRerankerType`
- `effectiveRerankerType`
- `rerankerModelName`
- `rerankerFingerprint`
- `rerankerInputCount`
- `rerankerOutputCount`
- `rerankerDurationMs`
- `rerankerFallbackUsed`
- `rerankerFallbackReason`
