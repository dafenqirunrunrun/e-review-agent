param(
  [string]$Python = "D:\anaconda\envs\torchtest\python.exe"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $root
try {
  & $Python .\ai-service\scripts\audit_realworld_source_licenses.py
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
  Pop-Location
}
