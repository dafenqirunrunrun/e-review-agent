param(
  [string]$Root = "",
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$MysqlDatabase = "litemall",
  [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"

. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "e-review-db-common.ps1")
$db = Get-EReviewDbConfig -Root $Root -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase

if (-not $OutputDir) {
  $OutputDir = Join-Path $db.Root "backups\db"
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = Join-Path $OutputDir "litemall_$timestamp.sql"

$previous = $env:MYSQL_PWD
try {
  $env:MYSQL_PWD = $db.Password
  & mysqldump "--default-character-set=utf8mb4" "-u$($db.User)" $db.Database "--result-file=$backupFile"
  if ($LASTEXITCODE -ne 0) {
    throw "mysqldump failed"
  }
} finally {
  $env:MYSQL_PWD = $previous
}

[ordered]@{
  backupFile = (Resolve-Path $backupFile).Path
  database = $db.Database
  result = "DB_BACKUP_PASS"
} | ConvertTo-Json -Depth 4
