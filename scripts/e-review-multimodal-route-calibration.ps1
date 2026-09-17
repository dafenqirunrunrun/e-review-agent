param(
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path

Push-Location $repoRoot
try {
  & $Python .\ai-service\scripts\calibrate_multimodal_human_review_route.py
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
