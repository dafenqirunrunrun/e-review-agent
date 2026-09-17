param(
  [string]$Root = "",
  [switch]$BuildBeforeStart
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = if ($Root) { (Resolve-Path $Root).Path } else { (Resolve-Path (Join-Path $scriptDir "..")).Path }

powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "e-review-stop-all.ps1")
Start-Sleep -Seconds 2

$args = @("-ExecutionPolicy", "Bypass", "-File", (Join-Path $scriptDir "e-review-start-all.ps1"), "-Root", $projectRoot)
if ($BuildBeforeStart) {
  $args += "-BuildBeforeStart"
}
powershell @args

Write-Host "RESTART_ALL_PASS"
