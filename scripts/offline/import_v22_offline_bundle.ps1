param(
  [Parameter(Mandatory = $true)][string]$BundleRoot,
  [Parameter(Mandatory = $true)][string]$ModelRoot,
  [Parameter(Mandatory = $false)][string]$SourceCommit = ""
)

$ErrorActionPreference = "Stop"

$bundle = Resolve-Path -LiteralPath $BundleRoot
$modelRootPath = New-Item -ItemType Directory -Force -Path $ModelRoot
$portable = Get-Content -LiteralPath "$bundle\metadata\v22-real-model-assets.portable.json" -Raw | ConvertFrom-Json

foreach ($section in @("reranker", "llm")) {
  $item = $portable.$section
  $source = Join-Path $bundle $item.relativePath
  $targetName = Split-Path $item.relativePath -Leaf
  $target = Join-Path $modelRootPath.FullName $targetName
  $partial = "$target.partial"
  if (Test-Path -LiteralPath $partial) {
    Remove-Item -LiteralPath $partial -Recurse -Force
  }
  if (Test-Path -LiteralPath $target) {
    $existing = Get-Content -LiteralPath "$target\MODEL_PROVENANCE.json" -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($existing.assetFingerprint -ne $item.assetFingerprint) {
      throw "Existing model directory has a different fingerprint: $target"
    }
    continue
  }
  Copy-Item -LiteralPath $source -Destination $partial -Recurse
  $prov = Get-Content -LiteralPath "$partial\MODEL_PROVENANCE.json" -Raw | ConvertFrom-Json
  if ($prov.assetFingerprint -ne $item.assetFingerprint) {
    throw "Imported model fingerprint mismatch: $targetName"
  }
  Rename-Item -LiteralPath $partial -NewName $targetName
}

$manifestDir = New-Item -ItemType Directory -Force -Path (Join-Path $modelRootPath.FullName "manifests")
$manifest = [ordered]@{
  schemaVersion = "2.0.0"
  sourceCommit = $SourceCommit
  embedding = @{
    modelId = "BAAI/bge-m3"
    provider = "flagembedding"
    modelPath = Join-Path (Split-Path $modelRootPath.FullName -Parent) "bge-m3"
    assetFingerprint = ""
    dimension = 1024
  }
  reranker = @{
    modelId = "BAAI/bge-reranker-v2-m3"
    provider = "flagembedding"
    modelPath = Join-Path $modelRootPath.FullName "bge-reranker-v2-m3"
    revision = $portable.reranker.revision
    assetFingerprint = $portable.reranker.assetFingerprint
    license = "Apache-2.0"
    architecture = "XLMRobertaForSequenceClassification"
  }
  llm = @{
    modelId = "Qwen/Qwen3-1.7B"
    provider = "local_qwen3_transformers"
    modelPath = Join-Path $modelRootPath.FullName "qwen3-1.7b"
    revision = $portable.llm.revision
    assetFingerprint = $portable.llm.assetFingerprint
    license = "Apache-2.0"
    architecture = "Qwen3ForCausalLM"
  }
}
Set-Content -LiteralPath "$($manifestDir.FullName)\v22-real-model-assets.json" -Value ($manifest | ConvertTo-Json -Depth 8) -Encoding UTF8
Write-Output "E_REVIEW_V22_OFFLINE_BUNDLE_IMPORTED"
