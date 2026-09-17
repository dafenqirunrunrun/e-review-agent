param(
  [string]$Python = "python",
  [string]$Tag = "v1.6.1-realworld-multimodal-evaluation"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $root
try {
  & $Python .\ai-service\scripts\v161_release_guard.py --tag $Tag
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
} finally {
  Pop-Location
}
