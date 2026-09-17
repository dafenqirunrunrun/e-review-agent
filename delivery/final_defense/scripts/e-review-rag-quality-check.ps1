param(
  [string]$Root = "",
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

if (-not $Root -or $Root.Trim().Length -eq 0) {
  $Root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
}

$script = Join-Path $Root "ai-service\scripts\evaluate_rag_quality.py"
$golden = Join-Path $Root "docs\eval\golden_rag_queries.jsonl"
$report = Join-Path $Root "docs\69_v12_rag_quality_report.md"

if (-not (Test-Path $script)) {
  throw "RAG evaluator not found: $script"
}
if (-not (Test-Path $golden)) {
  throw "Golden RAG query set not found: $golden"
}

Push-Location (Join-Path $Root "ai-service")
try {
  & $Python $script --input $golden --report $report
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
} finally {
  Pop-Location
}
