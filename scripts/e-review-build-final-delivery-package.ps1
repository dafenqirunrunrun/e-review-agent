param(
  [string]$Root = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = if ($Root) { (Resolve-Path $Root).Path } else { (Resolve-Path (Join-Path $scriptDir "..")).Path }
$deliveryRoot = Join-Path $projectRoot "delivery\final_defense"
$docsOut = Join-Path $deliveryRoot "docs"
$scriptsOut = Join-Path $deliveryRoot "scripts"
$reportsOut = Join-Path $deliveryRoot "reports"
$screenshotsOut = Join-Path $deliveryRoot "screenshots"

$dirs = @($deliveryRoot, $docsOut, $scriptsOut, $reportsOut, $screenshotsOut)
foreach ($dir in $dirs) {
  if (-not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
  }
}

$docNames = @(
  "16_demo_script.md",
  "17_screenshot_plan.md",
  "18_thesis_system_chapter_material.md",
  "22_v04_delivery_checklist.md",
  "25_fullstack_integration_test_report.md",
  "31_professional_agent_framework_integration.md",
  "35_deployment_and_startup_guide.md",
  "37_final_test_report.md",
  "39_project_completion_report.md",
  "44_defense_assets_plan.md",
  "45_demo_recording_script.md",
  "47_defense_qna.md",
  "48_v101_demo_stability_hotfix_report.md",
  "55_agent_quality_eval_report.md",
  "58_agent_rag_quality_eval_report.md",
  "69_v12_rag_quality_report.md",
  "78_one_click_startup_guide.md",
  "79_database_backup_restore_guide.md",
  "80_demo_mode_design.md",
  "81_error_handling_and_user_message_report.md",
  "82_security_hygiene_report.md",
  "83_thesis_system_design_material.md",
  "84_thesis_implementation_material.md",
  "85_thesis_testing_material.md",
  "86_thesis_deployment_material.md",
  "87_thesis_innovation_summary.md",
  "88_final_defense_delivery_index.md",
  "89_final_browser_regression_report.md"
)

$scriptNames = @(
  "e-review-start-all.ps1",
  "e-review-stop-all.ps1",
  "e-review-restart-all.ps1",
  "e-review-check-all.ps1",
  "e-review-open-demo-pages.ps1",
  "e-review-db-backup.ps1",
  "e-review-db-restore.ps1",
  "e-review-demo-data-reset.ps1",
  "e-review-db-check.ps1",
  "e-review-demo-mode-check.ps1",
  "e-review-error-message-check.ps1",
  "e-review-security-hygiene-check.ps1",
  "e-review-doc-link-check.ps1",
  "e-review-encoding-check.ps1",
  "e-review-zh-ui-text-check.ps1",
  "e-review-tool-protocol-check.ps1",
  "e-review-tool-schema-check.ps1",
  "e-review-rag-quality-check.ps1",
  "e-review-agentops-trend-check.ps1",
  "e-review-enterprise-agent-check.ps1",
  "e-review-full-ui-flow-check.ps1",
  "e-review-final-acceptance.ps1",
  "e-review-v12-acceptance.ps1",
  "e-review-graduation-final-check.ps1"
)

$missingDocs = @()
foreach ($name in $docNames) {
  $source = Join-Path (Join-Path $projectRoot "docs") $name
  if (Test-Path -LiteralPath $source) {
    Copy-Item -LiteralPath $source -Destination (Join-Path $docsOut $name) -Force
  } else {
    $missingDocs += $name
  }
}

$missingScripts = @()
foreach ($name in $scriptNames) {
  $source = Join-Path (Join-Path $projectRoot "scripts") $name
  if (Test-Path -LiteralPath $source) {
    Copy-Item -LiteralPath $source -Destination (Join-Path $scriptsOut $name) -Force
  } else {
    $missingScripts += $name
  }
}

$readme = Join-Path $deliveryRoot "README.md"
if (-not (Test-Path -LiteralPath $readme)) {
  @(
    "# E-Review Agent Final Defense Package",
    "",
    "Run e-review-build-final-delivery-package.ps1 from the project root to refresh this package."
  ) | Set-Content -LiteralPath $readme -Encoding UTF8
}

$forbidden = Get-ChildItem -LiteralPath $deliveryRoot -Recurse -Force | Where-Object {
  $_.FullName -match '\\(node_modules|target|dist|\.venv|__pycache__|\.pytest_cache|logs|backup|backups)\\'
}
if ($forbidden.Count -gt 0) {
  $forbidden | Select-Object FullName | ConvertTo-Json -Depth 3 | Write-Host
  throw "final delivery package contains forbidden generated files"
}

$sensitiveHits = @()
$privateUserPattern = -join @("C:", [char]0x5c, [char]0x5c, "Users", [char]0x5c, [char]0x5c)
$fileUriText = "file" + "://"
$knownPasswordPattern = "cfcs" + "20000731|litemall" + "123456"
$textFiles = Get-ChildItem -LiteralPath $deliveryRoot -Include *.md,*.ps1,*.txt -Recurse -File
foreach ($file in $textFiles) {
  $relative = $file.FullName.Replace($projectRoot + "\", "")
  $lines = Get-Content -LiteralPath $file.FullName -Encoding UTF8 -ErrorAction Stop
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match $privateUserPattern -or $lines[$i] -match [regex]::Escape($fileUriText) -or $lines[$i] -match $knownPasswordPattern) {
      if ($relative -like "delivery\final_defense\scripts\e-review-doc-link-check.ps1") { continue }
      if ($relative -like "delivery\final_defense\scripts\e-review-encoding-check.ps1") { continue }
      if ($relative -like "delivery\final_defense\scripts\e-review-error-message-check.ps1") { continue }
      if ($relative -like "delivery\final_defense\scripts\e-review-security-hygiene-check.ps1") { continue }
      $sensitiveHits += [ordered]@{
        file = $relative
        line = $i + 1
      }
    }
  }
}
if ($sensitiveHits.Count -gt 0) {
  $sensitiveHits | ConvertTo-Json -Depth 4 | Write-Host
  throw "final delivery package contains sensitive local data"
}

if ($missingDocs.Count -gt 0 -or $missingScripts.Count -gt 0) {
  [ordered]@{
    missingDocs = $missingDocs
    missingScripts = $missingScripts
  } | ConvertTo-Json -Depth 4 | Write-Host
  throw "final delivery package source files are incomplete"
}

[ordered]@{
  docs = $docNames.Count
  scripts = $scriptNames.Count
  deliveryRoot = "delivery\final_defense"
  result = "FINAL_DELIVERY_PACKAGE_PASS"
} | ConvertTo-Json -Depth 4
