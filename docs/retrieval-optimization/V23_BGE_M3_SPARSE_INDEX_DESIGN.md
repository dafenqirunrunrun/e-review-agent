# V2.3 BGE-M3 Sparse Index Design

Phase 9.4B uses a governed sparse inverted index backed by real BGE-M3 learned sparse weights.

The external index contains postings, chunk metadata, vector summaries and checksums. Repository artifacts only store hashes and aggregate counts.

Scoring uses `BGE_M3_LEARNED_SPARSE_DOT_PRODUCT` with deterministic tie-breaks: score descending, then chunkId ascending.

Invalid, expired, disabled, tombstoned and tenant-mismatched evidence is filtered before indexing.
