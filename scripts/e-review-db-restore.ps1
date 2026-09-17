param(
  [Parameter(Mandatory = $true)]
  [string]$SqlFile,
  [string]$Root = "",
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$MysqlDatabase = "litemall",
  [switch]$ConfirmRestore,
  [switch]$SecondConfirm
)

$ErrorActionPreference = "Stop"

if (-not $ConfirmRestore -or -not $SecondConfirm) {
  throw "restore requires -ConfirmRestore and -SecondConfirm"
}

. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "e-review-db-common.ps1")
$db = Get-EReviewDbConfig -Root $Root -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase

Invoke-EReviewMysqlFile -Db $db -SqlFile $SqlFile

Write-Host "DB_RESTORE_PASS"
