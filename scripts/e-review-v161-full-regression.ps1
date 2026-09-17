param(
  [string]$Python = "python",
  [string]$TorchPython = "D:\anaconda\envs\torchtest\python.exe",
  [string]$RerankerModelDir = "D:\EReviewAgent\models\rag-reranker",
  [string]$EmbeddingDevice = "cuda",
  [string]$RerankerDevice = "cuda",
  [string]$RealJson = "",
  [string]$VlmCandidates = "",
  [string]$TextModelDirs = "",
  [switch]$SkipBuilds
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$argsList = @(
  ".\ai-service\scripts\v161_full_regression.py",
  "--python", $Python,
  "--reranker-model-dir", $RerankerModelDir,
  "--embedding-device", $EmbeddingDevice,
  "--reranker-device", $RerankerDevice
)
if ($TorchPython.Trim().Length -gt 0) {
  $argsList += @("--torch-python", $TorchPython)
}
if ($RealJson.Trim().Length -gt 0) {
  $argsList += @("--real-json", $RealJson)
}
if ($VlmCandidates.Trim().Length -gt 0) {
  $argsList += @("--vlm-candidates", $VlmCandidates)
}
if ($TextModelDirs.Trim().Length -gt 0) {
  $argsList += @("--text-model-dirs", $TextModelDirs)
}
if ($SkipBuilds) {
  $argsList += "--skip-builds"
}

Push-Location $repoRoot
try {
  & $Python @argsList
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
