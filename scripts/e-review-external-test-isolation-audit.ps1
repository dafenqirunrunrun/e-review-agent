param(
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
  & $Python .\ai-service\scripts\audit_external_test_isolation.py
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
