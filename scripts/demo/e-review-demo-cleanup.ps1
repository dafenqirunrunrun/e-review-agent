param(
  [string]$Root = "",
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$MysqlDatabase = "litemall",
  [string]$TenantId = "demo-v2-tenant"
)

$ErrorActionPreference = "Stop"

. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\e-review-db-common.ps1")

$db = Get-EReviewDbConfig -Root $Root -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase
$sql = @"
DELETE o FROM litemall_agent_rag_override o
JOIN litemall_agent_rag_run r ON r.id = o.run_id
WHERE r.tenant_id='$TenantId' AND r.request_id LIKE 'demo-v2-%';
DELETE e FROM litemall_agent_rag_evidence e
JOIN litemall_agent_rag_run r ON r.id = e.run_id
WHERE r.tenant_id='$TenantId' AND r.request_id LIKE 'demo-v2-%';
DELETE FROM litemall_agent_rag_run
WHERE tenant_id='$TenantId' AND request_id LIKE 'demo-v2-%';
"@
$tmp = [System.IO.Path]::GetTempFileName()
try {
  Set-Content -LiteralPath $tmp -Value $sql -Encoding UTF8
  Invoke-EReviewMysqlFile -Db $db -SqlFile $tmp
} finally {
  Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}
Write-Host "E_REVIEW_DEMO_CLEANUP_PASS"
