param(
  [int[]]$Ports = @(8008, 8080, 8083, 6255, 9527)
)

$ErrorActionPreference = "Stop"

foreach ($port in $Ports) {
  $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if (-not $connections) {
    Write-Host "Port $port is not listening."
    continue
  }

  $processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($processId in $processIds) {
    try {
      $process = Get-Process -Id $processId -ErrorAction Stop
      Write-Host "Stopping port $port process $processId ($($process.ProcessName))..."
      Stop-Process -Id $processId -Force
    } catch {
      Write-Warning "Failed to stop process $processId on port ${port}: $($_.Exception.Message)"
    }
  }
}

Write-Host "Stop command completed."
