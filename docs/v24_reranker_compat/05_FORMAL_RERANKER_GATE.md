# Formal Reranker Gate

Classification: `BLOCKED`

Baseline formal runtime test:

```text
ai-service/tests/test_v200_agent_rag_phase3b_reranker.py::test_v22_real_reranker_executes_through_formal_agent_runtime
```

Result before fix:

```text
FAILED
ImportError: cannot import name 'is_torch_fx_available'
```

The post-fix formal runtime test and Phase 3B formal gate were not rerun because the dependency fix did not install. Re-running them before installing `FlagEmbedding==1.4.0` would only reproduce the known import failure.

No deterministic reranker, fallback, mock, hash scoring, or historical artifact was treated as a real reranker pass.
