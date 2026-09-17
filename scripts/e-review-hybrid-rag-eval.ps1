param(
  [string]$Python = $(if ($env:E_REVIEW_RAG_PYTHON) { $env:E_REVIEW_RAG_PYTHON } else { "python" }),
  [string]$ModelDir = $(if ($env:E_REVIEW_BGE_M3_MODEL_DIR) { $env:E_REVIEW_BGE_M3_MODEL_DIR } else { "D:\EReviewAgent\models\bge-m3" })
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$env:E_REVIEW_BGE_M3_MODEL_DIR = $ModelDir
Push-Location (Join-Path $repoRoot "ai-service")
try {
  & $Python ".\scripts\eval_hybrid_rag.py"
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
