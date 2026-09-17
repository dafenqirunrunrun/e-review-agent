param(
  [string]$Root = ""
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = if ($Root) { (Resolve-Path $Root).Path } else { (Resolve-Path (Join-Path $scriptDir "..")).Path }
$checkScript = Join-Path $projectRoot "scripts\check-services.ps1"

if (-not (Test-Path $checkScript)) {
  throw "check-services.ps1 not found"
}

$result = powershell -ExecutionPolicy Bypass -File $checkScript
$result | Write-Host

if (($result -join "`n") -notmatch '"result"\s*:\s*"PASS"') {
  throw "service check did not report PASS"
}

Write-Host "CHECK_ALL_PASS"
