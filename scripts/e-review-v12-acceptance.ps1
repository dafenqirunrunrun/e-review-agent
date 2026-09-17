param(
  [string]$Root = ""
)

$ErrorActionPreference = "Stop"

if (-not $Root -or $Root.Trim().Length -eq 0) {
  $Root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
}

function Invoke-Stage {
  param([string]$Name, [scriptblock]$Script)
  Write-Host "==== $Name ===="
  & $Script
  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed"
  }
}

Push-Location $Root
try {
  Invoke-Stage "doc-link-check" { powershell -ExecutionPolicy Bypass -File .\scripts\e-review-doc-link-check.ps1 }
  Invoke-Stage "encoding-check" { powershell -ExecutionPolicy Bypass -File .\scripts\e-review-encoding-check.ps1 }
  Invoke-Stage "zh-ui-text-check" { powershell -ExecutionPolicy Bypass -File .\scripts\e-review-zh-ui-text-check.ps1 }
  Invoke-Stage "tool-protocol-check" { powershell -ExecutionPolicy Bypass -File .\scripts\e-review-tool-protocol-check.ps1 }
  Invoke-Stage "tool-schema-check" { powershell -ExecutionPolicy Bypass -File .\scripts\e-review-tool-schema-check.ps1 }
  Invoke-Stage "rag-quality-check" { powershell -ExecutionPolicy Bypass -File .\scripts\e-review-rag-quality-check.ps1 }
  Invoke-Stage "agentops-trend-check" { powershell -ExecutionPolicy Bypass -File .\scripts\e-review-agentops-trend-check.ps1 }
  Invoke-Stage "enterprise-agent-check" { powershell -ExecutionPolicy Bypass -File .\scripts\e-review-enterprise-agent-check.ps1 }
  Invoke-Stage "full-ui-flow-check" { powershell -ExecutionPolicy Bypass -File .\scripts\e-review-full-ui-flow-check.ps1 }
  Invoke-Stage "final-acceptance" { powershell -ExecutionPolicy Bypass -File .\scripts\e-review-final-acceptance.ps1 }
} finally {
  Pop-Location
}

[ordered]@{
  result = "V12_ACCEPTANCE_PASS"
} | ConvertTo-Json -Depth 4
