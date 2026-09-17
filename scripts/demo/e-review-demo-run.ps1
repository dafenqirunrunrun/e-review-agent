param(
  [string]$Root = "",
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$MysqlDatabase = "litemall",
  [switch]$SkipSeed
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $SkipSeed) {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $scriptDir "e-review-demo-seed.ps1") -Root $Root -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase | Write-Host
}

. (Join-Path $scriptDir "..\e-review-db-common.ps1")
$db = Get-EReviewDbConfig -Root $Root -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase
$runs = Invoke-EReviewMysql -Db $db -Sql "SELECT request_id, risk_level, action FROM litemall_agent_rag_run WHERE tenant_id='demo-v2-tenant' AND request_id LIKE 'demo-v2-%' ORDER BY request_id;" -Raw

[ordered]@{
  schemaVersion = "1.0.0"
  adminUrl = "http://127.0.0.1:9527/#/agent-rag/overview"
  runListUrl = "http://127.0.0.1:9527/#/agent-rag/runs"
  syntheticRuns = @($runs)
  boundaries = @("Synthetic demo data only", "REAL_LLM_QUALITY_NOT_VERIFIED", "MODEL_RERANKER_NOT_VERIFIED")
} | ConvertTo-Json -Depth 6
Write-Host "E_REVIEW_DEMO_PASS"

