# V2 Reranker Baseline Audit

## Scope

This audit covers the Agent-RAG reranking layer before optional model reranker
activation. It does not introduce production claims and does not require a local
reranker model asset.

## Existing State

- Existing default reranker: deterministic lexical/fusion reranker.
- Existing retrieval path: BM25-first hybrid retrieval with optional real dense
  retrieval from Phase 3A.
- Model reranker status before this phase: `MODEL_RERANKER_NOT_VERIFIED`.
- Public release status: unchanged.

## Baseline Findings

- No `CrossEncoder` or `FlagReranker` integration was active in the Agent-RAG
  runtime path.
- `RAG_RERANKER_TYPE=deterministic` remains the safe default.
- Model paths are expected to stay outside Git.
- Reranker evidence fields were not previously explicit enough for enterprise
  audit review.

## Baseline Decision

The project now keeps deterministic reranking as the default and adds a governed
optional local model reranker layer. A real reranker is only considered verified
when a local model asset is configured, loaded, executed, and recorded in the
EvidenceBundle without fallback.
