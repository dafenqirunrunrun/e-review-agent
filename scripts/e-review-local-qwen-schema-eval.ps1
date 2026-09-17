param(
  [string]$BaseUrl = "http://127.0.0.1:8010",
  [string]$Python = "",
  [string]$ModelDir = "",
  [int]$Port = 8010
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
$aiService = Join-Path $root "ai-service"
$dataset = Join-Path $root "data\eval\review_schema_eval.jsonl"
$report = Join-Path $root "docs\100_v151_local_qwen_schema_eval_report.md"

if (-not $Python) {
  $Python = if ($env:E_REVIEW_LOCAL_QWEN_PYTHON) { $env:E_REVIEW_LOCAL_QWEN_PYTHON } else { "python" }
}
if (-not $ModelDir -and $env:E_REVIEW_LOCAL_QWEN_MODEL_DIR) {
  $ModelDir = $env:E_REVIEW_LOCAL_QWEN_MODEL_DIR
}

$startedProcess = $null
$previous = [ordered]@{
  Provider = $env:E_REVIEW_LLM_PROVIDER
  ModelDir = $env:E_REVIEW_LOCAL_QWEN_MODEL_DIR
  Thinking = $env:E_REVIEW_LOCAL_QWEN_ENABLE_THINKING
  Framework = $env:AGENT_FRAMEWORK_ENABLED
}

try {
  $healthy = $false
  try {
    $status = Invoke-RestMethod -Uri "$BaseUrl/api/v1/llm/provider/status" -TimeoutSec 5
    $healthy = $status.provider_name -eq "local_qwen3_transformers"
  } catch {
    $healthy = $false
  }

  if (-not $healthy) {
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
      throw "Port $Port is occupied by a non-local-Qwen service."
    }
    $env:E_REVIEW_LLM_PROVIDER = "local_qwen3_transformers"
    $env:E_REVIEW_LOCAL_QWEN_MODEL_DIR = $ModelDir
    $env:E_REVIEW_LOCAL_QWEN_ENABLE_THINKING = "false"
    $env:AGENT_FRAMEWORK_ENABLED = "false"
    $startedProcess = Start-Process -FilePath $Python -WorkingDirectory $aiService -WindowStyle Hidden -PassThru `
      -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port")
    $BaseUrl = "http://127.0.0.1:$Port"
    $ready = $false
    for ($attempt = 1; $attempt -le 60; $attempt++) {
      try {
        $health = Invoke-RestMethod -Uri "$BaseUrl/api/v1/health" -TimeoutSec 3
        if ($health.status -eq "ok") { $ready = $true; break }
      } catch {}
      Start-Sleep -Seconds 1
    }
    if (-not $ready) {
      throw "LOCAL_QWEN_SERVICE_START_FAILED"
    }
  }

  Push-Location $aiService
  try {
    & $Python .\scripts\eval_local_qwen_schema.py --base-url $BaseUrl --dataset $dataset --report $report
    $exitCode = $LASTEXITCODE
  } finally {
    Pop-Location
  }
  exit $exitCode
} finally {
  if ($startedProcess -and -not $startedProcess.HasExited) {
    Stop-Process -Id $startedProcess.Id -Force -ErrorAction SilentlyContinue
  }
  $env:E_REVIEW_LLM_PROVIDER = $previous.Provider
  $env:E_REVIEW_LOCAL_QWEN_MODEL_DIR = $previous.ModelDir
  $env:E_REVIEW_LOCAL_QWEN_ENABLE_THINKING = $previous.Thinking
  $env:AGENT_FRAMEWORK_ENABLED = $previous.Framework
}
