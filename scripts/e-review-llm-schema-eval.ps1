param(
    [string]$BaseUrl = "http://127.0.0.1:8008"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$aiService = Join-Path $repoRoot "ai-service"
$dataset = Join-Path $repoRoot "data\eval\review_schema_eval.jsonl"
$report = Join-Path $repoRoot "docs\96_v15_llm_json_schema_eval_report.md"

try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/api/v1/health" -TimeoutSec 5
    if ($health.status -ne "ok") {
        throw "AI service health response is not ok."
    }
} catch {
    Write-Error "AI service is unavailable at $BaseUrl. Start ai-service before evaluation."
    exit 1
}

Push-Location $aiService
try {
    python .\scripts\eval_llm_schema.py --base-url $BaseUrl --dataset $dataset --report $report
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
