param(
  [string]$Root = "",
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$MysqlDatabase = "litemall",
  [string]$OutputDir = "",
  [switch]$IncludeBusinessData
)

$ErrorActionPreference = "Stop"

. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\e-review-db-common.ps1")

$db = Get-EReviewDbConfig -Root $Root -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase
if (-not $OutputDir) {
  $runtime = if ($env:E_REVIEW_RUNTIME_HOME) { $env:E_REVIEW_RUNTIME_HOME } elseif ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA "EReviewAgent\runtime" } else { Join-Path $HOME ".e-review-agent\runtime" }
  $OutputDir = Join-Path $runtime "backups"
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$sqlFile = Join-Path $OutputDir "agent-rag-backup-$timestamp.sql"
$manifestFile = Join-Path $OutputDir "agent-rag-backup-$timestamp.manifest.json"
$tables = @(
  "litemall_agent_rag_schema_history",
  "litemall_agent_rag_run",
  "litemall_agent_rag_evidence",
  "litemall_agent_rag_override",
  "litemall_agent_rag_audit_chain"
)
if ($IncludeBusinessData) {
  $tables += @("litemall_ai_review_risk_task", "litemall_ai_operation_log")
}

$previous = $env:MYSQL_PWD
try {
  $env:MYSQL_PWD = $db.Password
  & mysqldump "--default-character-set=utf8mb4" "--single-transaction" "--no-tablespaces" "-u$($db.User)" $db.Database @tables "--result-file=$sqlFile"
  if ($LASTEXITCODE -ne 0) { throw "mysqldump failed" }
} finally {
  $env:MYSQL_PWD = $previous
}

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $sqlFile).Hash.ToLowerInvariant()
$manifest = [ordered]@{
  schemaVersion = "1.0.0"
  createdAt = (Get-Date).ToString("o")
  database = $db.Database
  includeBusinessData = [bool]$IncludeBusinessData
  tables = $tables
  backupFile = (Resolve-Path $sqlFile).Path
  sha256 = $hash
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $manifestFile
$manifest | ConvertTo-Json -Depth 6
Write-Host "E_REVIEW_BACKUP_PASS"
