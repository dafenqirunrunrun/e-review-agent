# Phase 3B Gate

## Issue Found

The Phase 3B readiness script manually constructed a narrow `RerankerConfig`, so it did not honor runtime environment settings such as timeout, batch size, max length, provider implementation, and FP16 mode.

This caused the formal test to pass while the standalone gate fell back with `EXECUTION_TIMEOUT`.

## Fix

The gate now uses `load_reranker_config(os.environ)` for the local-model attempt. If `RAG_RERANKER_MODEL_PATH` is absent, it intentionally ignores the asset manifest fallback so the existing "missing model path must block" behavior remains intact.

## Final Result

- Gate status: PASS
- `modelRerankerStatus`: PASS
- `effectiveType`: `local-model`
- `fallbackUsed`: false
- `modelName`: `BAAI/bge-reranker-v2-m3`

Evidence:

- `phase3b-gate-result-final.json`
- `phase3b-gate-final.log`
