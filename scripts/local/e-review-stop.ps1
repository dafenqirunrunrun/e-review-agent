param(
  [string]$RuntimeHome = $env:E_REVIEW_RUNTIME_HOME,
  [ValidateSet("ai-runtime", "admin-api", "admin-ui", "document-worker", "index-worker")]
  [string[]]$Component = @(),
  [switch]$All
)

$ErrorActionPreference = "Stop"

function Resolve-RuntimeHome {
  param([string]$Configured)
  if ($Configured) { return $Configured }
  if ($env:LOCALAPPDATA) { return (Join-Path $env:LOCALAPPDATA "EReviewAgent\runtime") }
  return (Join-Path $HOME ".e-review-agent\runtime")
}

$runtime = Resolve-RuntimeHome $RuntimeHome
$pidDir = Join-Path $runtime "pids"
if (-not (Test-Path $pidDir)) {
  Write-Host "No PID directory found: $pidDir"
  Write-Host "E_REVIEW_LOCAL_STOP_PASS"
  exit 0
}

function Stop-ProcessTree {
  param([int]$ProcessId)
  $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue
  foreach ($child in $children) { Stop-ProcessTree -ProcessId $child.ProcessId }
  if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
    Stop-Process -Id $ProcessId -Force
  }
}

$targets = if ($All -or $Component.Count -eq 0) { Get-ChildItem $pidDir -Filter "*.json" } else { $Component | ForEach-Object { Get-Item (Join-Path $pidDir "$_.json") -ErrorAction SilentlyContinue } }
foreach ($file in $targets) {
  if (-not $file) { continue }
  $record = Get-Content $file.FullName -Raw | ConvertFrom-Json
  $proc = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
  if ($proc) {
    Write-Host "Stopping $($record.name), PID=$($record.pid)"
    Stop-ProcessTree -ProcessId $record.pid
  } else {
    Write-Host "$($record.name) PID $($record.pid) is not running"
  }
  Remove-Item -LiteralPath $file.FullName -Force
}

Start-Sleep -Milliseconds 500

Write-Host "E_REVIEW_LOCAL_STOP_PASS"

