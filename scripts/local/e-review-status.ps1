param(
  [string]$RuntimeHome = $env:E_REVIEW_RUNTIME_HOME,
  [switch]$Json,
  [switch]$SkipWorkerCheck
)

$ErrorActionPreference = "Stop"

function Resolve-RuntimeHome {
  param([string]$Configured)
  if ($Configured) { return $Configured }
  if ($env:LOCALAPPDATA) { return (Join-Path $env:LOCALAPPDATA "EReviewAgent\runtime") }
  return (Join-Path $HOME ".e-review-agent\runtime")
}

function Test-Http {
  param([string]$Url)
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
    return [ordered]@{ ok = $true; statusCode = $response.StatusCode }
  } catch {
    return [ordered]@{ ok = $false; error = $_.Exception.Message }
  }
}

$runtime = Resolve-RuntimeHome $RuntimeHome
$pidDir = Join-Path $runtime "pids"
$records = @()
if (Test-Path $pidDir) {
  foreach ($file in Get-ChildItem $pidDir -Filter "*.json") {
    $record = Get-Content $file.FullName -Raw | ConvertFrom-Json
    $proc = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
    $records += [ordered]@{ name = $record.name; pid = $record.pid; port = $record.port; running = [bool]$proc }
  }
}

$summary = [ordered]@{
  schemaVersion = "1.0.0"
  runtimeHome = $runtime
  processes = $records
  services = [ordered]@{
    aiHealth = Test-Http "http://127.0.0.1:8008/api/v1/health"
    adminApi = Test-Http "http://127.0.0.1:8083/admin/auth/401"
    adminUi = Test-Http "http://127.0.0.1:9527"
  }
  workers = [ordered]@{
    documentWorker = [bool]($records | Where-Object { $_.name -eq "document-worker" -and $_.running })
    indexWorker = [bool]($records | Where-Object { $_.name -eq "index-worker" -and $_.running })
  }
  boundaries = @("REAL_LLM_QUALITY_NOT_VERIFIED", "MODEL_RERANKER_NOT_VERIFIED", "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED")
}
$serviceFailures = @($summary.services.Values | Where-Object { -not $_.ok })
$workerFailures = if ($SkipWorkerCheck) { @() } else { @($summary.workers.Values | Where-Object { -not $_ }) }
$summary["status"] = if ($serviceFailures.Count -eq 0 -and $workerFailures.Count -eq 0) { "PASS" } else { "FAIL" }
New-Item -ItemType Directory -Force -Path (Join-Path $runtime "status") | Out-Null
$summary | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 (Join-Path $runtime "status\status.json")

if ($Json) {
  $summary | ConvertTo-Json -Depth 8
} else {
  $summary.processes | ForEach-Object { Write-Host ("{0}: PID={1}, port={2}, running={3}" -f $_.name, $_.pid, $_.port, $_.running) }
  Write-Host "E_REVIEW_LOCAL_STATUS_$($summary.status)"
}

if ($summary.status -eq "PASS") { exit 0 } else { exit 1 }

