param(
  [string]$Root = "",
  [switch]$BuildBeforeStart
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = if ($Root) { (Resolve-Path $Root).Path } else { (Resolve-Path (Join-Path $scriptDir "..")).Path }
$startScript = Join-Path $projectRoot "scripts\start-all.ps1"
$checkScript = Join-Path $projectRoot "scripts\e-review-check-all.ps1"

if (-not (Test-Path $startScript)) {
  throw "start-all.ps1 not found"
}

$args = @("-ExecutionPolicy", "Bypass", "-File", $startScript, "-Root", $projectRoot)
if ($BuildBeforeStart) {
  $args += "-BuildBeforeStart"
}

powershell @args
powershell -ExecutionPolicy Bypass -File $checkScript -Root $projectRoot

Write-Host "START_ALL_PASS"
