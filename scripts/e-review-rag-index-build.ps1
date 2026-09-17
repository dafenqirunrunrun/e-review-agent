param(
  [string]$Python = $(if ($env:E_REVIEW_RAG_PYTHON) { $env:E_REVIEW_RAG_PYTHON } else { "python" }),
  [string]$ModelDir = $(if ($env:E_REVIEW_BGE_M3_MODEL_DIR) { $env:E_REVIEW_BGE_M3_MODEL_DIR } else { "D:\EReviewAgent\models\bge-m3" })
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$aiService = Join-Path $repoRoot "ai-service"
$env:E_REVIEW_EMBEDDING_PROVIDER = "bge_m3"
$env:E_REVIEW_BGE_M3_MODEL_DIR = $ModelDir
$env:E_REVIEW_EMBEDDING_DEVICE = $(if ($env:E_REVIEW_EMBEDDING_DEVICE) { $env:E_REVIEW_EMBEDDING_DEVICE } else { "cuda" })

Push-Location $aiService
try {
  & $Python ".\scripts\build_rag_index.py"
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
