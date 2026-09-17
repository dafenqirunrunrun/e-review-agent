# Agent-RAG Phase 3A Implementation Audit

## Scope

Phase 3A adds optional real dense retrieval for the internal E-Review Agent
Agent-RAG runtime. It does not remove the Phase 2 fixture-hash mode and does
not make BGE-M3 a service startup dependency.

## Repository Baseline

- Branch: `experiment/v2.0-agent-rag-governed-runtime`
- Starting HEAD: `7f83a3db84b59d4d0b1a0e8a7b933ad56cec89de`
- Push: `NO_PUSH`
- Tag: `NO_TAG`
- Release: `NO_RELEASE`

## Environment

- Python: `3.10.0`
- Torch: `2.5.1+cu121`
- CUDA available: `true`
- FAISS: `1.8.0`
- BGE-M3 asset: present in a repo-external local model directory
- `pip check`: failed because `pytest 8.3.5 requires tomli`

The BGE-M3 model directory is configured through `RAG_BGE_M3_MODEL_PATH`.
The full local path is intentionally not recorded in project documents.

## Reused Code

- Phase 2 knowledge contracts and ingestion.
- Phase 2 BM25, hash dense fixture, RRF fusion, deterministic reranker and
  evidence quality semantics.
- Earlier FAISS ideas were inspected, but Phase 3A uses Agent-RAG specific
  provider, manifest and gate code.

## Fixture vs Real Boundaries

- `fixture-hash` remains available for fast deterministic tests.
- `real-dense` means BGE-M3 embeddings plus FAISS `IndexFlatIP`.
- `hybrid-real` means BM25 plus BGE-M3/FAISS plus RRF and deterministic rerank.
- Hash fallback is explicitly marked as fallback and is never reported as
  `bge-m3`.

## Current Gaps

- Model reranker is not verified.
- Real LLM answer quality is not verified.
- Large-scale or production concurrency is not verified.
- No production Enterprise RAG claim is made.
