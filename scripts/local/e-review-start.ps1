param(
  [string]$RuntimeHome = $env:E_REVIEW_RUNTIME_HOME,
  [string]$Python = $env:E_REVIEW_PYTHON,
  [string]$Java = $env:E_REVIEW_JAVA,
  [string]$Profile = "local",
  [switch]$SkipFrontend,
  [switch]$SkipAi,
  [switch]$SkipWorkers,
  [switch]$NoMigration,
  [switch]$KeepExisting
)

$ErrorActionPreference = "Stop"

function Resolve-RuntimeHome {
  param([string]$Configured)
  if ($Configured) { return $Configured }
  if ($env:LOCALAPPDATA) { return (Join-Path $env:LOCALAPPDATA "EReviewAgent\runtime") }
  return (Join-Path $HOME ".e-review-agent\runtime")
}

function Assert-PortAvailable {
  param([int]$Port, [string]$Name)
  $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($conn -and -not $KeepExisting) {
    throw "$Name port $Port is already listening at PID $($conn.OwningProcess). Use -KeepExisting to reuse it."
  }
  return [bool]$conn
}

function Start-ManagedProcess {
  param(
    [string]$Name,
    [string]$WorkingDirectory,
    [string]$FilePath,
    [string[]]$Arguments = @(),
    [int]$Port = 0
  )
  $pidFile = Join-Path $script:PidDir "$Name.json"
  if ($Port -gt 0 -and (Assert-PortAvailable -Port $Port -Name $Name)) {
    Write-Host "$Name already running on port $Port; keeping existing process."
    return
  }
  if ($Port -eq 0 -and (Test-Path $pidFile)) {
    $existing = Get-Content $pidFile -Raw | ConvertFrom-Json
    if (Get-Process -Id $existing.pid -ErrorAction SilentlyContinue) {
      if ($KeepExisting) {
        Write-Host "$Name already running at PID $($existing.pid); keeping existing process."
        return
      }
      throw "$Name is already running at PID $($existing.pid). Stop the local stack first or use -KeepExisting."
    }
    Remove-Item -LiteralPath $pidFile -Force
  }
  $stdout = Join-Path $script:LogDir "$Name.out.log"
  $stderr = Join-Path $script:LogDir "$Name.err.log"
  $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory `
    -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  [ordered]@{
    name = $Name
    pid = $process.Id
    port = $Port
    startedAt = (Get-Date).ToString("o")
    cwd = $WorkingDirectory
    executable = $FilePath
    arguments = $Arguments
  } | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $pidFile
  $target = if ($Port -gt 0) { "port $Port" } else { "background worker" }
  Write-Host "Started $Name on $target. PID=$($process.Id)"
}

function Wait-Port {
  param([int]$Port, [string]$Name, [int]$TimeoutSeconds = 90)
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($connection) { return }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)
  throw "$Name did not start listening on port $Port within $TimeoutSeconds seconds."
}

function Wait-Http {
  param([string]$Url, [string]$Name, [int]$TimeoutSeconds = 90)
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    try {
      $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return }
    } catch {}
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)
  throw "$Name did not become HTTP-ready within $TimeoutSeconds seconds."
}

function Assert-ManagedProcessAlive {
  param([string]$Name)
  $record = Get-Content (Join-Path $script:PidDir "$Name.json") -Raw | ConvertFrom-Json
  if (-not (Get-Process -Id $record.pid -ErrorAction SilentlyContinue)) {
    $errorLog = Join-Path $script:LogDir "$Name.err.log"
    $tail = if (Test-Path $errorLog) { (Get-Content $errorLog -Tail 8) -join " | " } else { "no error log" }
    throw "$Name exited during startup: $tail"
  }
}

$root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\..")).Path
$runtime = Resolve-RuntimeHome $RuntimeHome
$venvPython = Join-Path $root "ai-service\.venv\Scripts\python.exe"
$Python = if ($Python) { $Python } elseif (Test-Path $venvPython) { $venvPython } else { "python" }
$Java = if ($Java) { $Java } else { "java" }
$script:PidDir = Join-Path $runtime "pids"
$script:LogDir = Join-Path $runtime "logs"
New-Item -ItemType Directory -Force -Path $runtime, $script:PidDir, $script:LogDir, (Join-Path $runtime "status") | Out-Null

& (Join-Path $root "scripts\local\e-review-doctor.ps1") -RuntimeHome $runtime -Python $Python | Write-Host

if (-not $NoMigration) {
  $migration = Join-Path $root "scripts\database\e-review-migrate.ps1"
  if (Test-Path $migration) {
    powershell -NoProfile -ExecutionPolicy Bypass -File $migration -Status | Write-Host
  } else {
    Write-Host "Migration script not present yet; skipping migration status for this phase."
  }
}

if (-not $SkipAi) {
  $oldRuntimeHome = $env:E_REVIEW_RUNTIME_HOME
  $oldRagEnabled = $env:AGENT_RAG_ENABLED
  $oldRagMode = $env:AGENT_RAG_TARGET_MODE
  try {
    $env:E_REVIEW_RUNTIME_HOME = $runtime
    $env:AGENT_RAG_ENABLED = "true"
    $env:AGENT_RAG_TARGET_MODE = "enterprise-maturity-local-single-node"
    Start-ManagedProcess -Name "ai-runtime" -WorkingDirectory (Join-Path $root "ai-service") -Port 8008 `
      -FilePath $Python -Arguments @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8008")
  } finally {
    $env:E_REVIEW_RUNTIME_HOME = $oldRuntimeHome
    $env:AGENT_RAG_ENABLED = $oldRagEnabled
    $env:AGENT_RAG_TARGET_MODE = $oldRagMode
  }
}

$adminJarRelative = $env:E_REVIEW_ADMIN_JAR
if (-not $adminJarRelative) { $adminJarRelative = "litemall-admin-api\target\litemall-admin-api-0.1.0-exec.jar" }
$adminJar = Join-Path $root $adminJarRelative
if (-not (Test-Path $adminJar)) { throw "Admin API jar not found. Run mvn -DskipTests package first: $adminJar" }
$previousWorkerToken = $env:DOCUMENT_WORKER_TOKEN
try {
  if (-not $env:DOCUMENT_WORKER_TOKEN) {
    if ($KeepExisting -and (Get-NetTCPConnection -LocalPort 8083 -State Listen -ErrorAction SilentlyContinue) -and -not $SkipWorkers) {
      throw "Cannot attach workers to an existing Admin API without an explicit DOCUMENT_WORKER_TOKEN."
    }
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $env:DOCUMENT_WORKER_TOKEN = [Convert]::ToBase64String($bytes)
  }
  Start-ManagedProcess -Name "admin-api" -WorkingDirectory $root -Port 8083 -FilePath $Java `
    -Arguments @("-jar", $adminJar, "--server.port=8083", "--server.address=127.0.0.1", "--spring.profiles.active=db,core,admin", "--spring.servlet.multipart.max-file-size=20MB", "--spring.servlet.multipart.max-request-size=21MB")

  if (-not $SkipWorkers) {
    Start-ManagedProcess -Name "document-worker" -WorkingDirectory (Join-Path $root "ai-service") `
      -FilePath $Python -Arguments @("-u", "scripts/document_job_worker.py")
    Start-ManagedProcess -Name "index-worker" -WorkingDirectory (Join-Path $root "ai-service") `
      -FilePath $Python -Arguments @("-u", "scripts/document_index_worker.py")
  }
} finally {
  $env:DOCUMENT_WORKER_TOKEN = $previousWorkerToken
}

if (-not $SkipFrontend) {
  $npm = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
  if (-not $npm) { $npm = "npm" }
  Start-ManagedProcess -Name "admin-ui" -WorkingDirectory (Join-Path $root "litemall-admin") -Port 9527 `
    -FilePath $npm -Arguments @("run", "dev")
}

if (-not $SkipAi) { Wait-Port -Port 8008 -Name "ai-runtime" }
Wait-Port -Port 8083 -Name "admin-api"
if (-not $SkipFrontend) { Wait-Port -Port 9527 -Name "admin-ui" }
if (-not $SkipAi) { Wait-Http -Url "http://127.0.0.1:8008/api/v1/health" -Name "ai-runtime" }
Wait-Http -Url "http://127.0.0.1:8083/admin/auth/401" -Name "admin-api"
if (-not $SkipFrontend) { Wait-Http -Url "http://127.0.0.1:9527" -Name "admin-ui" }
if (-not $SkipWorkers) {
  Assert-ManagedProcessAlive -Name "document-worker"
  Assert-ManagedProcessAlive -Name "index-worker"
}

$statusArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $root "scripts\local\e-review-status.ps1"), "-RuntimeHome", $runtime)
if ($SkipWorkers) { $statusArgs += "-SkipWorkerCheck" }
powershell @statusArgs | Write-Host
if ($LASTEXITCODE -ne 0) { throw "Local runtime status check failed." }
Write-Host "E_REVIEW_LOCAL_START_PASS"
