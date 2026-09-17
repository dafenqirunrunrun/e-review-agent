# Full Test Report

Classification: `NOT_RUN`

Python full regression was not rerun because the minimal dependency fix was not applied.

Known baseline from this isolated environment:

- Formal reranker test: `FAILED`
- Root cause: `FlagEmbedding==1.3.5` and `transformers==5.3.0` import incompatibility

After the offline wheel is installed, rerun:

```powershell
D:\anaconda\envs\ereview-v24-reranker-fix\python.exe -m pytest ai-service/tests -v -rA --tb=short --junitxml=docs/v24_reranker_compat/test-results/python-full.xml
```

Acceptance target remains `0 failed`.
