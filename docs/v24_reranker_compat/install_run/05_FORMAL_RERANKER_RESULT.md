# Formal Reranker Result

## Test

`ai-service/tests/test_v200_agent_rag_phase3b_reranker.py::test_v22_real_reranker_executes_through_formal_agent_runtime`

## Result

PASS.

The formal runtime test executed through the Agent RAG runtime using the real local FlagEmbedding reranker asset.

Environment highlights:

- `RAG_RERANKER_PROVIDER_IMPL=flagembedding`
- `RAG_RERANKER_MODEL_PATH=D:\EReviewAgent\models\v2.2\bge-reranker-v2-m3`
- `RAG_RERANKER_DEVICE=cuda`
- `RAG_RERANKER_USE_FP16=true`
- `RAG_RERANKER_TIMEOUT_MS=45000`

Evidence:

- `formal-reranker-after-fix.log`
- `formal-reranker-after-fix.xml`
