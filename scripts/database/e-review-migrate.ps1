param(
  [string]$Root = "",
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$MysqlDatabase = "litemall",
  [switch]$Status,
  [switch]$Apply,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\e-review-db-common.ps1")

function Get-FileSha256 {
  param([string]$Path)
  return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Get-CanonicalLfFileSha256 {
  param([string]$Path)
  $utf8Strict = [System.Text.UTF8Encoding]::new($false, $true)
  $text = [System.IO.File]::ReadAllText($Path, $utf8Strict)
  if ($text.Length -gt 0 -and $text[0] -eq [char]0xFEFF) {
    $text = $text.Substring(1)
  }
  $text = $text -replace "`r`n", "`n"
  $text = $text -replace "`r", "`n"
  $text = ($text -replace "`n*$", "") + "`n"
  $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($text)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    return ([System.BitConverter]::ToString($sha.ComputeHash($bytes)) -replace "-", "").ToLowerInvariant()
  } finally {
    $sha.Dispose()
  }
}

function Get-MigrationChecksum {
  param([string]$Path, [object]$Migration)
  $algorithm = if ($Migration.checksumAlgorithm) { [string]$Migration.checksumAlgorithm } else { "sha256-raw-bytes" }
  if ($algorithm -eq "sha256-canonical-lf-v1") {
    return Get-CanonicalLfFileSha256 -Path $Path
  }
  if ($algorithm -eq "sha256-raw-bytes") {
    return Get-FileSha256 -Path $Path
  }
  throw "Unsupported migration checksum algorithm: $algorithm"
}

function Test-ApprovedMigrationChecksum {
  param([object]$Migration, [string]$HistoryChecksum, [string]$CurrentChecksum)
  if (-not $HistoryChecksum) { return $true }
  if ($HistoryChecksum -eq $CurrentChecksum) { return $true }
  if ($Migration.canonicalChecksum -and $CurrentChecksum -ne $Migration.canonicalChecksum) {
    return $false
  }
  foreach ($legacy in @($Migration.approvedLegacyChecksums)) {
    if ($legacy.algorithm -eq "sha256-raw-bytes" -and $legacy.checksum -eq $HistoryChecksum) {
      return $true
    }
  }
  return $false
}

function Invoke-Scalar {
  param([hashtable]$Db, [string]$Sql)
  $rows = Invoke-EReviewMysql -Db $Db -Sql $Sql -Raw
  if ($rows) { return (($rows | Select-Object -First 1) -split "\s+")[0] }
  return ""
}

function Test-Table {
  param([hashtable]$Db, [string]$Table)
  $count = Invoke-Scalar -Db $Db -Sql "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='$Table';"
  return [int]$count -gt 0
}

function Test-Column {
  param([hashtable]$Db, [string]$Table, [string]$Column)
  $count = Invoke-Scalar -Db $Db -Sql "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='$Table' AND column_name='$Column';"
  return [int]$count -gt 0
}

function Ensure-History {
  param([hashtable]$Db)
  Invoke-EReviewMysql -Db $Db -Sql @"
CREATE TABLE IF NOT EXISTS litemall_agent_rag_schema_history (
  version VARCHAR(64) NOT NULL PRIMARY KEY,
  description VARCHAR(255) NOT NULL,
  script VARCHAR(255) NOT NULL,
  checksum CHAR(64) NOT NULL,
  installed_at DATETIME NOT NULL,
  success TINYINT(1) NOT NULL DEFAULT 1,
  execution_note VARCHAR(255) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"@ | Out-Null
}

function Get-HistoryChecksum {
  param([hashtable]$Db, [string]$Version)
  return Invoke-Scalar -Db $Db -Sql "SELECT checksum FROM litemall_agent_rag_schema_history WHERE version='$Version' AND success=1;"
}

function Add-History {
  param([hashtable]$Db, [object]$Migration, [string]$Checksum, [string]$Note)
  $description = ($Migration.description -replace "'", "''")
  $script = ($Migration.script -replace "'", "''")
  Invoke-EReviewMysql -Db $Db -Sql "INSERT INTO litemall_agent_rag_schema_history(version, description, script, checksum, installed_at, success, execution_note) VALUES('$($Migration.version)', '$description', '$script', '$Checksum', NOW(), 1, '$Note') ON DUPLICATE KEY UPDATE checksum=VALUES(checksum), success=1, execution_note=VALUES(execution_note);" | Out-Null
}

function Test-MigrationAlreadyPresent {
  param([hashtable]$Db, [object]$Migration)
  foreach ($table in @($Migration.requiredTables)) {
    if (-not (Test-Table -Db $Db -Table $table)) { return $false }
  }
  if ($Migration.requiredColumns) {
    foreach ($property in $Migration.requiredColumns.PSObject.Properties) {
      foreach ($column in @($property.Value)) {
        if (-not (Test-Column -Db $Db -Table $property.Name -Column $column)) { return $false }
      }
    }
  }
  return $true
}

$db = Get-EReviewDbConfig -Root $Root -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase
$manifestPath = Join-Path $db.Root "scripts\database\agent-rag-migrations.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
Ensure-History -Db $db

$results = @()
foreach ($migration in $manifest.migrations) {
  $scriptPath = Join-Path $db.Root $migration.script
  if (-not (Test-Path $scriptPath)) { throw "Migration SQL not found: $scriptPath" }
  $checksum = Get-MigrationChecksum -Path $scriptPath -Migration $migration
  if ($migration.canonicalChecksum -and $checksum -ne $migration.canonicalChecksum) {
    throw "Canonical checksum mismatch for migration $($migration.version)"
  }
  $historyChecksum = Get-HistoryChecksum -Db $db -Version $migration.version
  $alreadyPresent = Test-MigrationAlreadyPresent -Db $db -Migration $migration
  $state = if ($historyChecksum) { "installed" } elseif ($alreadyPresent) { "already-present" } else { "pending" }

  if ($historyChecksum -and -not (Test-ApprovedMigrationChecksum -Migration $migration -HistoryChecksum $historyChecksum -CurrentChecksum $checksum)) {
    throw "Checksum mismatch for migration $($migration.version)"
  }
  if ($Apply -and -not $historyChecksum) {
    if ($alreadyPresent) {
      Add-History -Db $db -Migration $migration -Checksum $checksum -Note "already-present"
      $state = "installed"
    } else {
      Invoke-EReviewMysqlFile -Db $db -SqlFile $scriptPath
      Add-History -Db $db -Migration $migration -Checksum $checksum -Note "applied"
      $state = "installed"
    }
  }

  $results += [ordered]@{
    version = $migration.version
    description = $migration.description
    script = $migration.script
    checksumAlgorithm = if ($migration.checksumAlgorithm) { $migration.checksumAlgorithm } else { "sha256-raw-bytes" }
    checksum = $checksum
    historyChecksum = $historyChecksum
    state = $state
  }
}

$pending = @($results | Where-Object { $_.state -eq "pending" })
$summary = [ordered]@{
  schemaVersion = "1.0.0"
  status = if ($pending.Count -eq 0 -or $DryRun -or $Status) { "PASS" } else { "PENDING" }
  database = $db.Database
  migrations = $results
  pendingCount = $pending.Count
}
$summary | ConvertTo-Json -Depth 8
if ($Apply -and $pending.Count -eq 0) { Write-Host "E_REVIEW_DATABASE_MIGRATION_PASS" }
elseif ($Status -or $DryRun) { Write-Host "E_REVIEW_DATABASE_MIGRATION_STATUS_PASS" }

