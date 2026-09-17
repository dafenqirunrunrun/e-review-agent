param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
Push-Location $repoRoot
try { & $Python .\ai-service\scripts\eval_multimodal_ablation.py; exit $LASTEXITCODE } finally { Pop-Location }
