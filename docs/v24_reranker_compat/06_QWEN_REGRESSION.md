# Qwen Regression

Classification: `NOT_RUN`

Qwen regression was intentionally not run after the blocked dependency installation because the environment did not change. The last canonical validation already confirmed Qwen runtime smoke in the separate canonical evidence worktree, but this stage does not reuse that as a new regression pass.

After installing `FlagEmbedding==1.4.0` offline, rerun:

```powershell
$env:AGENT_LLM_MODEL_PATH = "D:\EReviewAgent\models\v2.2\qwen3-1.7b"
D:\anaconda\envs\ereview-v24-reranker-fix\python.exe ai-service/scripts/qualification/run_v22_real_llm_smoke.py
```

Required checks:

- `fallbackUsed=false`
- `realGenerate=true`
- `schemaValid=true`
