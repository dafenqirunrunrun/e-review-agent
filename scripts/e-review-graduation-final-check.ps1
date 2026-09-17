param(
  [string]$Root = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = if ($Root) { (Resolve-Path $Root).Path } else { (Resolve-Path (Join-Path $scriptDir "..")).Path }

function Invoke-Gate {
  param(
    [string]$Name,
    [string[]]$Markers
  )

  $scriptPath = Join-Path (Join-Path $projectRoot "scripts") $Name
  if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "missing gate script: $Name"
  }

  Write-Host "==> $Name"
  Push-Location $projectRoot
  try {
    $output = & powershell -ExecutionPolicy Bypass -File $scriptPath 2>&1
    $exitCode = $LASTEXITCODE
  } finally {
    Pop-Location
  }

  $text = ($output | Out-String)
  Write-Host $text
  if ($exitCode -ne 0) {
    throw "$Name failed with exit code $exitCode"
  }

  foreach ($marker in $Markers) {
    if ($text -notmatch [regex]::Escape($marker)) {
      throw "$Name did not output marker $marker"
    }
  }
}

$gates = @(
  @{ name = "e-review-check-all.ps1"; markers = @("CHECK_ALL_PASS") },
  @{ name = "e-review-db-check.ps1"; markers = @("DB_CHECK_PASS") },
  @{ name = "e-review-demo-mode-check.ps1"; markers = @("DEMO_MODE_CHECK_PASS") },
  @{ name = "e-review-doc-link-check.ps1"; markers = @("DOC_LINK_CHECK_PASS") },
  @{ name = "e-review-encoding-check.ps1"; markers = @("ENCODING_CHECK_PASS") },
  @{ name = "e-review-zh-ui-text-check.ps1"; markers = @("ZH_UI_TEXT_CHECK_PASS") },
  @{ name = "e-review-error-message-check.ps1"; markers = @("ERROR_MESSAGE_CHECK_PASS") },
  @{ name = "e-review-security-hygiene-check.ps1"; markers = @("SECURITY_HYGIENE_CHECK_PASS") },
  @{ name = "e-review-tool-protocol-check.ps1"; markers = @("TOOL_PROTOCOL_CHECK_PASS") },
  @{ name = "e-review-tool-schema-check.ps1"; markers = @("TOOL_SCHEMA_CHECK_PASS") },
  @{ name = "e-review-rag-quality-check.ps1"; markers = @("RAG_QUALITY_CHECK_PASS") },
  @{ name = "e-review-agentops-trend-check.ps1"; markers = @("AGENTOPS_TREND_CHECK_PASS") },
  @{ name = "e-review-enterprise-agent-check.ps1"; markers = @("ENTERPRISE_AGENT_CHECK_PASS") },
  @{ name = "e-review-full-ui-flow-check.ps1"; markers = @("FULL_UI_FLOW_PASS", "CUSTOMER_ADMIN_END_TO_END_PASS") },
  @{ name = "e-review-final-acceptance.ps1"; markers = @("FINAL_ACCEPTANCE_PASS") },
  @{ name = "e-review-v12-acceptance.ps1"; markers = @("V12_ACCEPTANCE_PASS") },
  @{ name = "e-review-build-final-delivery-package.ps1"; markers = @("FINAL_DELIVERY_PACKAGE_PASS") }
)

$passed = @()
foreach ($gate in $gates) {
  Invoke-Gate -Name $gate.name -Markers $gate.markers
  $passed += $gate.name
}

[ordered]@{
  passedGates = $passed.Count
  gates = $passed
  result = "GRADUATION_FINAL_CHECK_PASS"
} | ConvertTo-Json -Depth 4

Write-Host "GRADUATION_FINAL_CHECK_PASS"
