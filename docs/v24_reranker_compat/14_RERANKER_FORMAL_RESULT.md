# Reranker Formal Result

Classification: `NOT_RUN_AFTER_PLAN_A_BLOCKED`

The original failing formal reranker test was not rerun under `transformers==4.51.3` because the 4.51.3 stack could not be installed.

Known baseline from Stage 1.2A:

```text
FAILED
ImportError: cannot import name 'is_torch_fx_available'
```

No deterministic reranker, fallback, mock, hash score, asset-only check, or historical artifact was treated as a real reranker pass.

After the offline wheelhouse is installed, rerun:

```powershell
$env:AGENT_RAG_V22_ASSET_MANIFEST = "D:\EReviewAgent\models\v2.2\manifests\v22-real-model-assets.json"
$env:RAG_RERANKER_TYPE = "local-model"
$env:RAG_RERANKER_PROVIDER = "flagembedding"
$env:RAG_RERANKER_MODEL_PATH = "D:\EReviewAgent\models\v2.2\bge-reranker-v2-m3"
$env:RAG_RERANKER_DEVICE = "cuda"
$env:RAG_RERANKER_USE_FP16 = "true"
D:\anaconda\envs\ereview-v24-transformers451\python.exe -m pytest ai-service/tests/test_v200_agent_rag_phase3b_reranker.py::test_v22_real_reranker_executes_through_formal_agent_runtime -v -rA --tb=long
```
