param(
  [Parameter(Mandatory = $true)]
  [string]$ManifestFile,
  [string]$Root = "",
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$MysqlDatabase = "litemall",
  [switch]$VerifyOnly,
  [switch]$Restore,
  [switch]$ConfirmRestore
)

$ErrorActionPreference = "Stop"

. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\e-review-db-common.ps1")

if (-not (Test-Path -LiteralPath $ManifestFile)) { throw "Manifest not found: $ManifestFile" }
$manifest = Get-Content -LiteralPath $ManifestFile -Raw | ConvertFrom-Json
$sqlFile = $manifest.backupFile
if (-not (Test-Path -LiteralPath $sqlFile)) { throw "Backup SQL not found: $sqlFile" }
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $sqlFile).Hash.ToLowerInvariant()
if ($hash -ne $manifest.sha256) { throw "Backup checksum mismatch" }

if ($Restore) {
  if (-not $ConfirmRestore) { throw "Restore requires -ConfirmRestore" }
  $db = Get-EReviewDbConfig -Root $Root -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase
  Invoke-EReviewMysqlFile -Db $db -SqlFile $sqlFile
  Write-Host "E_REVIEW_RESTORE_PASS"
} else {
  Write-Host "E_REVIEW_RESTORE_VERIFY_PASS"
}

[ordered]@{
  schemaVersion = "1.0.0"
  status = "PASS"
  verifyOnly = [bool]$VerifyOnly
  restore = [bool]$Restore
  manifest = (Resolve-Path $ManifestFile).Path
  sha256 = $hash
} | ConvertTo-Json -Depth 6

