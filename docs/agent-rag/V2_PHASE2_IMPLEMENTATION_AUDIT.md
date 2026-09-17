# v2.0 Agent-RAG Phase 2 Implementation Audit

## Phase 1 Fixture Boundary

Phase 1 used a 30-case fixture with deterministic BM25/Hybrid retrieval over
in-memory chunks. Its latency values represented lightweight local execution,
not real embedding, FAISS, reranker, or LLM latency.

## Real Components Already Reused

- BM25 tokenization/scoring from `ai-service/app/rag/sparse_retriever.py`.
- Hash dense adapter from `ai-service/app/rag/dense_retriever.py` for fixture
  dense-mode comparisons.
- Tenant normalization from `ai-service/app/rag/tenant_acl.py`.
- Stable hashing from `ai-service/app/rag/document_contract.py`.

## Deterministic Simulation

- Dense retrieval in this phase is `fixture_hash_dense`, not BGE-M3.
- Reranking defaults to deterministic lexical overlap plus fused rank.
- `FailingModelReranker` verifies fallback semantics; it is not a model.

## Directly Reusable

- Document and chunk contracts.
- Ingestion validation, deduplication, and manifest generation.
- Single-process atomic activation and rollback semantics.
- RRF fusion and evidence quality gate.

## Must Be Replaced Or Revalidated Later

- Hash dense adapter must be replaced by BGE-M3 + FAISS for real retrieval
  quality claims.
- Deterministic reranker must be replaced or explicitly retained as fallback
  before claiming model reranker quality.
- Fixture benchmark must be extended with larger, independently audited
  knowledge before production claims.

## Retained Fallbacks

- Deterministic reranker fallback.
- Empty retrieval returns no fabricated citation.
- Retired, disabled, expired, future, and cross-tenant evidence are filtered.
