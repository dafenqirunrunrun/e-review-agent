# Agent-RAG Phase 3A BGE-M3 Provider

## Configuration

The provider is controlled by local environment variables:

- `RAG_DENSE_PROVIDER=bge-m3`
- `RAG_BGE_M3_MODEL_PATH`
- `RAG_BGE_M3_DEVICE`
- `RAG_BGE_M3_BATCH_SIZE`
- `RAG_BGE_M3_MAX_LENGTH`
- `RAG_BGE_M3_NORMALIZE`
- `RAG_BGE_M3_LOAD_ON_STARTUP`

Default `.env.example` keeps `RAG_DENSE_PROVIDER=hash` so a missing local model
does not break startup.

## Verified Local Evidence

- Provider: `bge-m3`
- Model name: `BAAI/bge-m3`
- Model fingerprint: `de91a4787c227ad8d177386408fd01cea14b28e829a1e01576ba4ef2523b8a7c`
- Device: `cuda`
- Embedding dimension: `1024`
- Normalize: `true`
- Cold start: `24200 ms`
- First embedding: `49 ms`
- CUDA allocated peak: `2206 MB`
- CUDA reserved peak: `2228 MB`

## Validation Rules

The provider rejects:

- empty batches
- empty text
- non-2D embeddings
- NaN or Inf vectors
- zero or invalid dimensions
- non-normalized vectors when normalization is enabled

The model fingerprint does not include user names, machine names, absolute
paths or file timestamps.
