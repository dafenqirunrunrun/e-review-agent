param(
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$Database = "litemall",
  [string]$SqlFile = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "e-review-db-common.ps1")
$db = Get-EReviewDbConfig -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $Database
$MysqlUser = $db.User
$MysqlPassword = $db.Password
$Database = $db.Database

if (-not $SqlFile -or $SqlFile.Trim().Length -eq 0) {
  $root = (Resolve-Path (Join-Path $scriptDir "..")).Path
  if (Test-Path (Join-Path $root "litemall-db\sql\litemall_ai_demo_seed.sql")) {
    $SqlFile = Join-Path $root "litemall-db\sql\litemall_ai_demo_seed.sql"
  } else {
    $SqlFile = Join-Path $root "litemall\litemall-db\sql\litemall_ai_demo_seed.sql"
  }
}

if (-not (Test-Path $SqlFile)) {
  throw "Seed SQL file not found: $SqlFile"
}

Write-Host "Seeding E-Review Agent demo data..."
$previous = $env:MYSQL_PWD
try {
  $env:MYSQL_PWD = $MysqlPassword
  Get-Content -LiteralPath $SqlFile -Raw | & mysql "-u$MysqlUser" $Database
  if ($LASTEXITCODE -ne 0) {
    throw "mysql seed command failed with exit code $LASTEXITCODE"
  }
} finally {
  $env:MYSQL_PWD = $previous
}

$countSql = "select 'analysis' as table_name, count(*) as total from litemall_review_ai_analysis where review_id like 'EREVIEW-DEMO-%' union all select 'risk_task', count(*) from litemall_ai_review_risk_task where review_id like 'EREVIEW-DEMO-%' union all select 'operation_log', count(*) from litemall_ai_operation_log where risk_task_id in (select id from litemall_ai_review_risk_task where review_id like 'EREVIEW-DEMO-%') union all select 'demo_review', count(*) from litemall_ai_demo_review where nickname='demo-seed';"
try {
  $env:MYSQL_PWD = $MysqlPassword
  & mysql "-u$MysqlUser" $Database -e $countSql
} finally {
  $env:MYSQL_PWD = $previous
}
