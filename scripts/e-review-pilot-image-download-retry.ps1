param(
  [string]$Python = "D:\anaconda\envs\torchtest\python.exe"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
  & $Python .\ai-service\scripts\retry_pilot_image_downloads.py
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
