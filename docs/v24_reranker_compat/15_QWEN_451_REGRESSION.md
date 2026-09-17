# Qwen 4.51.3 Regression

Classification: `NOT_RUN`

Qwen regression was not run under `transformers==4.51.3` because the target stack was not installed.

This run does not claim that Qwen works or fails under Transformers 4.51.3. Plan B is therefore not justified yet.

After installing the offline wheelhouse, run:

```powershell
$env:AGENT_LLM_MODEL_PATH = "D:\EReviewAgent\models\v2.2\qwen3-1.7b"
D:\anaconda\envs\ereview-v24-transformers451\python.exe ai-service/scripts/qualification/run_v22_real_llm_smoke.py
```

Required result:

```text
fallbackUsed=false
realGenerate=true
schemaValid=true
```
