param(
  [string]$PythonExe = "python",
  [string]$ManifestPath = $env:AGENT_RAG_V22_ASSET_MANIFEST,
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
  [string]$IndexRoot = "",
  [string]$DenseProviderImpl = "flagembedding",
  [int]$Port = 8008
)

$ErrorActionPreference = "Stop"

if (-not $ManifestPath) {
  throw "AGENT_RAG_V22_ASSET_MANIFEST is required."
}
if (-not (Test-Path $ManifestPath)) {
  throw "ManifestPath does not exist."
}
if (-not $IndexRoot) {
  $IndexRoot = Join-Path $RepoRoot "artifacts\agent-rag\v2.0-phase3a2\faiss-bge-m3"
}
if (-not (Test-Path $IndexRoot)) {
  throw "IndexRoot does not exist."
}

$assets = Get-Content -Raw $ManifestPath | ConvertFrom-Json
$aiRoot = Join-Path $RepoRoot "ai-service"
$logDir = Join-Path $RepoRoot "artifacts\real-model-chain\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$env:AGENT_RAG_V22_ASSET_MANIFEST = $ManifestPath
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:PYTHONPATH = $aiRoot

$env:RAG_DENSE_PROVIDER = "bge-m3"
$env:RAG_BGE_M3_PROVIDER_IMPL = $DenseProviderImpl
$env:RAG_BGE_M3_MODEL_PATH = $assets.embedding.modelPath
$env:RAG_BGE_M3_DEVICE = "cuda"
$env:RAG_BGE_M3_BATCH_SIZE = "4"
$env:RAG_BGE_M3_MAX_LENGTH = "512"
$env:RAG_BGE_M3_NORMALIZE = "true"
$env:RAG_BGE_M3_USE_FP16 = "true"
$env:RAG_REAL_DENSE_REQUIRED = "true"
$env:RAG_INDEX_ROOT = $IndexRoot
$env:RAG_DEFAULT_RETRIEVAL_MODE = "hybrid-real"

$env:RAG_RERANKER_TYPE = "local-model"
$env:RAG_RERANKER_PROVIDER_IMPL = "flagembedding"
$env:RAG_RERANKER_DEVICE = "cuda"
$env:RAG_RERANKER_BATCH_SIZE = "4"
$env:RAG_RERANKER_MAX_LENGTH = "384"
$env:RAG_RERANKER_CANDIDATE_K = "12"
$env:RAG_RERANKER_FINAL_K = "5"
$env:RAG_REAL_RERANKER_REQUIRED = "true"

$env:AGENT_LLM_PROVIDER = "local_qwen3_transformers"
$env:AGENT_LLM_MODEL_PATH = $assets.llm.modelPath
$env:AGENT_LLM_DEVICE = "cuda"
$env:AGENT_LLM_DTYPE = "float16"
$env:AGENT_LLM_ENABLE_THINKING = "false"
$env:AGENT_LLM_MAX_INPUT_TOKENS = "2048"
$env:AGENT_LLM_MAX_OUTPUT_TOKENS = "256"
$env:AGENT_REAL_LLM_REQUIRED = "true"

$env:AGENT_MODEL_RESIDENCY_MODE = "exclusive-model-slot"
$env:AGENT_GPU_MIN_FREE_MEMORY_MB = "768"

$stdout = Join-Path $logDir "python-$Port.out.log"
$stderr = Join-Path $logDir "python-$Port.err.log"
$process = Start-Process `
  -FilePath $PythonExe `
  -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", [string]$Port) `
  -WorkingDirectory $aiRoot `
  -WindowStyle Hidden `
  -RedirectStandardOutput $stdout `
  -RedirectStandardError $stderr `
  -PassThru

$process.Id | Set-Content -Encoding ascii (Join-Path $logDir "python-$Port.pid")
[pscustomobject]@{
  pid = $process.Id
  port = $Port
  stdout = $stdout
  stderr = $stderr
}
