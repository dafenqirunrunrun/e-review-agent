# V2.3 Parent-Child Hierarchy Design

## Goal

Phase 9.5A evaluates whether deterministic Document/Section/Chunk hierarchy can recover evidence that flat child retrieval leaves at deep ranks. This is a controlled replacement hypothesis after the Sparse route was closed for v2.3.

## Unit Contract

- Document: governed knowledge document.
- Parent Unit: document section when present, otherwise document root.
- Child Unit: existing `KnowledgeChunk`.

Parent IDs are deterministic hashes over tenant, document, and section path. The implementation does not use database row order, random UUIDs, LLM summaries, generated keywords, HyDE text, or query labels.

## Parent Content

Parent content is built from deterministic fields only:

- document title
- section path
- child text ordered by `chunkIndex` and `chunkId`

Two bounded representations are supported for calibration:

- `P1`: title + section path + section child contents
- `P2`: section path + section child contents

The parent builder supports max token limits of 256 and 512 and reports truncation. Artifacts store content hashes and summary statistics, not full parent or child content.

## Governance Boundary

- `maximumFinalK = 5`
- `allowBackfill = false`
- eligibility rules are unchanged
- no Sparse, Multi-vector, HyDE, Query2doc, query normalization, LLM parent summary, or model reranker is introduced
