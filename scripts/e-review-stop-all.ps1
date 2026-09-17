param(
  [int[]]$Ports = @(8008, 8080, 8083, 6255, 9527)
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$stopScript = Join-Path $scriptDir "stop-all.ps1"

if (-not (Test-Path $stopScript)) {
  throw "stop-all.ps1 not found"
}

powershell -ExecutionPolicy Bypass -File $stopScript -Ports $Ports

$stillListening = @()
foreach ($port in $Ports) {
  $connection = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($connection) {
    $stillListening += $port
  }
}

if ($stillListening.Count -gt 0) {
  throw "ports still listening after stop: $($stillListening -join ',')"
}

Write-Host "STOP_ALL_PASS"
