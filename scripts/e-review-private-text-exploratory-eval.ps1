param(
  [int]$PerSource = 30,
  [int]$StabilityPerSource = 5,
  [int]$Seed = 162,
  [string]$Python = $env:E_REVIEW_PYTHON,
  [string]$ModelDir = $env:E_REVIEW_LOCAL_QWEN_MODEL_DIR
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
  $Python = "python"
}
if (-not $ModelDir) {
  $ModelDir = Join-Path (Split-Path -Parent $Root) "models\Qwen3-1.7B"
}

powershell -ExecutionPolicy Bypass `
  -File "$Root\scripts\e-review-wait-for-gpu.ps1" `
  -Stage "private-text-exploratory-evaluation" `
  -MinFreeMemoryMB 5200 `
  -CheckIntervalSeconds 30 `
  -StableChecks 3 `
  -TimeoutSeconds 0

$env:E_REVIEW_LLM_PROVIDER = "local_qwen3_transformers"
$env:E_REVIEW_LOCAL_QWEN_MODEL_DIR = $ModelDir
$env:E_REVIEW_LOCAL_QWEN_MAX_NEW_TOKENS = "96"
$env:E_REVIEW_LOCAL_QWEN_ENABLE_THINKING = "false"

& $Python "$Root\ai-service\scripts\eval_private_real_text_exploratory.py" --per-source $PerSource --stability-per-source $StabilityPerSource --seed $Seed
