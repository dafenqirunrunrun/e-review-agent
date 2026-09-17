param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
Push-Location $repoRoot
try { & $Python .\ai-service\scripts\eval_vlm_visual_evidence.py; exit $LASTEXITCODE } finally { Pop-Location }
