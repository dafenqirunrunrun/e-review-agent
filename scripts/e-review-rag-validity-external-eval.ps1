param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
Push-Location $repoRoot
try { & $Python .\ai-service\scripts\eval_rag_validity_and_external.py; exit $LASTEXITCODE } finally { Pop-Location }
