param(
  [string]$Root = "",
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$MysqlDatabase = "litemall"
)

$ErrorActionPreference = "Stop"

. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "e-review-db-common.ps1")
$db = Get-EReviewDbConfig -Root $Root -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase

$requiredTables = @(
  "litemall_comment",
  "litemall_review_ai_analysis",
  "litemall_ai_review_risk_task",
  "litemall_ai_operation_log",
  "litemall_ai_agent_run",
  "litemall_ai_agent_step",
  "litemall_ai_agent_feedback",
  "litemall_ai_tool_registry",
  "litemall_ai_memory_profile",
  "litemall_ai_guardrail_event"
)

$missingTables = @()
foreach ($table in $requiredTables) {
  $count = Invoke-EReviewMysql -Db $db -Raw -Sql "select count(1) from information_schema.tables where table_schema=database() and table_name='$table';"
  if ([int](($count | Select-Object -Last 1).Trim()) -ne 1) {
    $missingTables += $table
  }
}

if ($missingTables.Count -gt 0) {
  throw "missing core tables: $($missingTables -join ',')"
}

$requiredColumns = @(
  @{ table = "litemall_review_ai_analysis"; column = "source_type" },
  @{ table = "litemall_review_ai_analysis"; column = "source_id" },
  @{ table = "litemall_ai_review_risk_task"; column = "source_type" },
  @{ table = "litemall_ai_review_risk_task"; column = "source_id" },
  @{ table = "litemall_ai_agent_run"; column = "status" },
  @{ table = "litemall_ai_agent_run"; column = "state_snapshot_json" },
  @{ table = "litemall_ai_agent_step"; column = "status" },
  @{ table = "litemall_ai_agent_step"; column = "agent_role" },
  @{ table = "litemall_ai_agent_step"; column = "agent_goal" },
  @{ table = "litemall_ai_agent_step"; column = "tool_name" }
)

$missingColumns = @()
foreach ($item in $requiredColumns) {
  $count = Invoke-EReviewMysql -Db $db -Raw -Sql "select count(1) from information_schema.columns where table_schema=database() and table_name='$($item.table)' and column_name='$($item.column)';"
  if ([int](($count | Select-Object -Last 1).Trim()) -ne 1) {
    $missingColumns += "$($item.table).$($item.column)"
  }
}

if ($missingColumns.Count -gt 0) {
  throw "missing migration columns: $($missingColumns -join ',')"
}

$demoProducts = Invoke-EReviewMysql -Db $db -Raw -Sql @"
select count(1)
from litemall_goods g
join litemall_goods_product p on p.goods_id = g.id and p.deleted = 0
where g.id in (1181000,1006007,1006013)
  and g.deleted = 0
  and g.is_on_sale = 1
group by g.id
having sum(p.number) > 0;
"@

if (($demoProducts | Where-Object { $_.Trim() -match '^\d+$' }).Count -lt 3) {
  throw "demo products are not all purchasable"
}

Invoke-EReviewMysql -Db $db -Sql "create temporary table if not exists e_review_db_check_tmp(id int primary key); insert into e_review_db_check_tmp(id) values(1) on duplicate key update id=values(id); drop temporary table e_review_db_check_tmp;" | Out-Null

[ordered]@{
  coreTables = $requiredTables.Count
  migrationColumns = $requiredColumns.Count
  demoProducts = 3
  aiTablesWritable = $true
  result = "DB_CHECK_PASS"
} | ConvertTo-Json -Depth 4
