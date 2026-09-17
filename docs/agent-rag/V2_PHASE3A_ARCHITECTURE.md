# Agent-RAG Phase 3A Architecture

## Main Flow

```text
KnowledgeChunk
-> EmbeddingProvider
-> normalized vector
-> FAISS IndexFlatIP
-> manifest validation
-> atomic activation
-> BGE-M3 dense retrieval
-> BM25 fusion
-> deterministic rerank
-> evidence quality gate
-> Agent evidence bundle
```

## Providers

Phase 3A defines a pluggable embedding protocol:

- `HashEmbeddingProvider`: deterministic fixture mode.
- `BgeM3EmbeddingProvider`: real local BGE-M3 provider.
- `DisabledEmbeddingProvider`: explicit disabled/degraded state.

Provider methods:

- `embed_documents(texts)`
- `embed_query(text)`
- `health()`
- `metadata()`
- `close()`

The real provider is lazy by default. A missing or failing model does not stop
the whole AI service.

## Runtime Modes

- `fixture-hash`: Phase 2 compatible deterministic mode.
- `real-dense`: BGE-M3 plus FAISS only.
- `hybrid-real`: BM25 plus BGE-M3/FAISS plus RRF.
- `sparse-only`: explicit degraded mode.

Every runtime result records:

- requested retrieval mode
- effective retrieval mode
- dense provider
- fallback flag and reason
- model fingerprint
- index version
- embedding and FAISS search latency

## Safety

FAISS candidates are still filtered by tenant and metadata after vector search.
Vector search cannot bypass tenant isolation or disabled/deleted knowledge
status.
