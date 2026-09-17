# Agent-RAG Phase 3A FAISS Index

## Index

- FAISS type: `IndexFlatIP`
- Metric: `inner-product`
- Intended similarity: cosine similarity over normalized embeddings
- Vector count in verified run: `474`
- Index version: `phase3a-eval-real-v1`
- Index checksum: `70080bf85f04f58e964f7814576f90e9564badfa4c0db1cccaefc83f7c0babe3`
- Metadata checksum: `8be303885f2cc7871c34a408c607d1538ad49289af1d823e377a629bf1c57c5b`

Generated FAISS files are written under ignored artifact/index locations and
must not be committed.

## Metadata Mapping

Each vector stores a metadata row containing:

- vector position
- chunk ID
- document ID
- tenant ID
- content hash
- document version
- status
- effective time
- source type
- title and text

The index is invalid if metadata count and vector count differ.

## Compatibility Gate

Activation is blocked when:

- model fingerprint mismatches
- embedding dimension mismatches
- normalization setting mismatches
- index type or metric mismatches
- tenant mismatches
- index or metadata checksums mismatch
- manifest or index files are missing

The active index pointer is updated atomically with a small text pointer file.
Rollback validates compatibility before reactivation.
