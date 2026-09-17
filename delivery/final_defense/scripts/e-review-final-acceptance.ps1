param(
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$MysqlDatabase = "litemall"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "e-review-db-common.ps1")
$db = Get-EReviewDbConfig -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase
$MysqlUser = $db.User
$MysqlPassword = $db.Password
$MysqlDatabase = $db.Database

function Invoke-Stage {
  param(
    [string]$Name,
    [scriptblock]$Block
  )
  Write-Host "==== $Name ===="
  try {
    $output = & $Block
    [ordered]@{
      name = $Name
      status = "PASS"
      output = $output
    }
  } catch {
    [ordered]@{
      name = $Name
      status = "FAIL"
      error = $_.Exception.Message
    }
  }
}

$results = @()
$results += Invoke-Stage "check-services" { powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "check-services.ps1") }
$results += Invoke-Stage "seed-demo-products" { powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "seed-demo-products.ps1") -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase }
$results += Invoke-Stage "smoke" { powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "e-review-smoke.ps1") }
$results += Invoke-Stage "admin-full-menu-api" { powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "e-review-admin-full-menu-api-check.ps1") }
$results += Invoke-Stage "admin-api-matrix" { powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "e-review-admin-api-matrix-check.ps1") }
$results += Invoke-Stage "customer-loop" { powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "e-review-customer-loop-check.ps1") -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase }
$results += Invoke-Stage "agent-framework" { powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "e-review-agent-framework-check.ps1") }
$results += Invoke-Stage "encoding-check" { powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "e-review-encoding-check.ps1") }
$results += Invoke-Stage "agent-quality-check" { powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "e-review-agent-quality-check.ps1") }
$results += Invoke-Stage "rag-quality-check" { powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "e-review-rag-quality-check.ps1") }
$results += Invoke-Stage "enterprise-agent-check" { powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "e-review-enterprise-agent-check.ps1") }
$results += Invoke-Stage "full-ui-flow" { powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "e-review-full-ui-flow-check.ps1") -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase }
$results += Invoke-Stage "doc-link-check" { powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "e-review-doc-link-check.ps1") }
$results += Invoke-Stage "database-consistency" {
  $sql = @"
select 'duplicate_analysis' as check_name, count(*) as issue_count
from (
  select source_type, source_id, count(*) c
  from litemall_review_ai_analysis
  where deleted = 0 and source_type is not null and source_id is not null
  group by source_type, source_id
  having c > 1
) t
union all
select 'risk_without_analysis', count(*)
from litemall_ai_review_risk_task r
left join litemall_review_ai_analysis a on r.analysis_id = a.id
where r.deleted = 0 and (r.analysis_id is not null and a.id is null)
union all
select 'duplicate_risk_task', count(*)
from (
  select analysis_id, risk_type, count(*) c
  from litemall_ai_review_risk_task
  where deleted = 0
  group by analysis_id, risk_type
  having c > 1
) t
union all
select 'orphan_feedback', count(*)
from litemall_ai_agent_feedback f
left join litemall_ai_review_risk_task r on f.risk_task_id = r.id
left join litemall_review_ai_analysis a on f.analysis_id = a.id
where f.deleted = 0
  and ((f.risk_task_id is not null and r.id is null)
    or (f.analysis_id is not null and a.id is null))
union all
select 'agent_run_without_step', count(*)
from litemall_ai_agent_run r
left join litemall_ai_agent_step s on r.id = s.run_id
where r.deleted = 0 and s.id is null
union all
select 'agent_step_without_run', count(*)
from litemall_ai_agent_step s
left join litemall_ai_agent_run r on s.run_id = r.id
where s.deleted = 0 and r.id is null
union all
select 'stale_running_run', count(*)
from litemall_ai_agent_run
where deleted = 0 and status = 'running' and created_time < date_sub(now(), interval 5 minute)
union all
select 'stale_running_patrol', count(*)
from litemall_ai_patrol_log
where status = 'running' and created_time < date_sub(now(), interval 5 minute);
"@
  $previous = $env:MYSQL_PWD
  try {
    $env:MYSQL_PWD = $MysqlPassword
    $rows = & mysql "-u$MysqlUser" "-N" "-D" $MysqlDatabase "-e" $sql
    if ($LASTEXITCODE -ne 0) {
      throw "mysql consistency check failed"
    }
  } finally {
    $env:MYSQL_PWD = $previous
  }
  $bad = $rows | Where-Object { ($_ -split "\s+")[-1] -ne "0" }
  if ($bad) {
    throw "database consistency issues: $($bad -join '; ')"
  }
  $rows
}

$failed = $results | Where-Object { $_.status -ne "PASS" }
[ordered]@{
  stages = $results
  result = if ($failed) { "FAIL" } else { "FINAL_ACCEPTANCE_PASS" }
} | ConvertTo-Json -Depth 8

if ($failed) {
  exit 1
}
