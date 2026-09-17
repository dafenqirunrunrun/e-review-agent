param(
  [Parameter(Mandatory = $true)][string]$BundleRoot,
  [Parameter(Mandatory = $true)][string]$OnlinePython,
  [string]$TargetPythonVersion = "3.10",
  [int]$MaxWorkers = 2
)

$ErrorActionPreference = "Stop"

$bundle = Resolve-Path -LiteralPath (New-Item -ItemType Directory -Force -Path $BundleRoot)
New-Item -ItemType Directory -Force -Path "$bundle\wheelhouse", "$bundle\models", "$bundle\metadata" | Out-Null

& $OnlinePython -m pip download `
  --only-binary=:all: `
  --no-deps `
  --dest "$bundle\wheelhouse" `
  "transformers==4.51.3" `
  "tokenizers==0.21.1" `
  "huggingface-hub==0.30.2" `
  "safetensors==0.5.3"

& $OnlinePython ".\scripts\models\download_v22_real_models.py" `
  --all `
  --target-root "$bundle\models" `
  --max-workers $MaxWorkers

$wheelEntries = @()
Get-ChildItem -LiteralPath "$bundle\wheelhouse" -Filter *.whl | Sort-Object Name | ForEach-Object {
  $parts = $_.BaseName -split "-"
  $wheelEntries += [ordered]@{
    filename = $_.Name
    sizeBytes = $_.Length
    sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
    packageName = $parts[0]
    packageVersion = $parts[1]
    pythonTag = if ($parts.Count -ge 3) { $parts[2] } else { "" }
    abiTag = if ($parts.Count -ge 4) { $parts[3] } else { "" }
    platformTag = if ($parts.Count -ge 5) { $parts[4] } else { "any" }
  }
}

$wheelManifest = [ordered]@{
  schemaVersion = "1.0.0"
  onlinePythonVersion = (& $OnlinePython -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")
  targetPythonVersion = $TargetPythonVersion
  targetPlatform = "Windows x64"
  createdAtUtc = (Get-Date).ToUniversalTime().ToString("o")
  wheels = $wheelEntries
}
$wheelJson = $wheelManifest | ConvertTo-Json -Depth 8
Set-Content -LiteralPath "$bundle\metadata\wheelhouse-manifest.json" -Value $wheelJson -Encoding UTF8

$rerankerProv = Get-Content -LiteralPath "$bundle\models\bge-reranker-v2-m3\MODEL_PROVENANCE.json" -Raw | ConvertFrom-Json
$llmProv = Get-Content -LiteralPath "$bundle\models\qwen3-1.7b\MODEL_PROVENANCE.json" -Raw | ConvertFrom-Json
$portable = [ordered]@{
  schemaVersion = "2.0.0"
  embedding = @{ status = "external-existing"; modelId = "BAAI/bge-m3"; provider = "flagembedding"; dimension = 1024 }
  reranker = @{
    modelId = "BAAI/bge-reranker-v2-m3"
    relativePath = "models/bge-reranker-v2-m3"
    revision = $rerankerProv.resolvedRevision
    assetFingerprint = $rerankerProv.assetFingerprint
    license = "Apache-2.0"
  }
  llm = @{
    modelId = "Qwen/Qwen3-1.7B"
    relativePath = "models/qwen3-1.7b"
    revision = $llmProv.resolvedRevision
    assetFingerprint = $llmProv.assetFingerprint
    license = "Apache-2.0"
  }
}
Set-Content -LiteralPath "$bundle\metadata\v22-real-model-assets.portable.json" -Value ($portable | ConvertTo-Json -Depth 8) -Encoding UTF8

$files = @()
Get-ChildItem -LiteralPath $bundle -File -Recurse |
  Where-Object { $_.FullName -notlike "*\.git\*" -and $_.FullName -notlike "*\.cache\*" -and $_.Name -ne "bundle-manifest.json" -and $_.Name -ne "SHA256SUMS" } |
  Sort-Object FullName |
  ForEach-Object {
    $rel = Resolve-Path -LiteralPath $_.FullName -Relative
    $rel = $rel.TrimStart(".\").Replace("\", "/")
    $files += [ordered]@{
      relativePath = $rel
      sizeBytes = $_.Length
      sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant()
    }
  }

$wheelHash = (Get-FileHash -Algorithm SHA256 -LiteralPath "$bundle\metadata\wheelhouse-manifest.json").Hash.ToLowerInvariant()
$portableHash = (Get-FileHash -Algorithm SHA256 -LiteralPath "$bundle\metadata\v22-real-model-assets.portable.json").Hash.ToLowerInvariant()
$bundleManifest = [ordered]@{
  schemaVersion = "1.0.0"
  bundleId = "e-review-v22-" + (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")
  createdAtUtc = (Get-Date).ToUniversalTime().ToString("o")
  targetPlatform = "Windows x64"
  targetPython = $TargetPythonVersion
  sourceModelRevisions = @{
    reranker = $rerankerProv.resolvedRevision
    llm = $llmProv.resolvedRevision
  }
  wheelhouseManifestHash = $wheelHash
  portableAssetManifestHash = $portableHash
  allFileCount = $files.Count
  allFileBytes = ($files | Measure-Object -Property sizeBytes -Sum).Sum
  files = $files
}
Set-Content -LiteralPath "$bundle\bundle-manifest.json" -Value ($bundleManifest | ConvertTo-Json -Depth 12) -Encoding UTF8
($files | ForEach-Object { "$($_.sha256)  $($_.relativePath)" }) | Set-Content -LiteralPath "$bundle\SHA256SUMS" -Encoding UTF8

Write-Output "E_REVIEW_V22_OFFLINE_BUNDLE_PREPARED"
