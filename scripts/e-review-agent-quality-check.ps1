param(
  [string]$Root = "",
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

if (-not $Root -or $Root.Trim().Length -eq 0) {
  $Root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
}

$script = Join-Path $Root "ai-service\scripts\evaluate_agent_quality.py"
$golden = Join-Path $Root "docs\eval\golden_reviews.jsonl"
$report = Join-Path $Root "docs\58_agent_rag_quality_eval_report.md"
$legacyReport = Join-Path $Root "docs\55_agent_quality_eval_report.md"

if (-not (Test-Path $script)) {
  throw "Quality evaluator not found: $script"
}
if (-not (Test-Path $golden)) {
  throw "Golden review set not found: $golden"
}

Push-Location (Join-Path $Root "ai-service")
try {
  & $Python $script --input $golden --report $report --legacy-report $legacyReport
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
} finally {
  Pop-Location
}
