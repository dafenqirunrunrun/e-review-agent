# Full Test Report

## Command

`python -m pytest ai-service/tests -v -rA --tb=short`

## Result

- collected: 620
- passed: 604
- skipped: 16
- failed: 0
- duration: 227.83 seconds

The skipped cases are model-asset-gated tests that require explicit real asset environment variables. The formal real reranker, Phase 3B gate, Qwen smoke, and BGE smoke were executed separately with explicit real-model configuration and passed.

Evidence:

- `python-full-transformers451.log`
- `python-full-transformers451.xml`
- `python-full-transformers451-exit.txt`
