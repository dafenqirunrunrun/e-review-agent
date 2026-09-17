param(
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
  & $Python .\ai-service\scripts\v161_requirement_traceability.py
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
