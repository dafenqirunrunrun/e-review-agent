param(
  [string]$JavaExe = "java",
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
  [string]$JarPath = "",
  [int]$Port = 8083,
  [string]$SingleTenantId = "__local__",
  [int]$ReadTimeoutMs = 180000,
  [int]$TotalTimeoutMs = 210000
)

$ErrorActionPreference = "Stop"

if (-not $JarPath) {
  $JarPath = Join-Path $RepoRoot "litemall-admin-api\target\litemall-admin-api-0.1.0-exec.jar"
}
if (-not (Test-Path $JarPath)) {
  throw "JarPath does not exist."
}

$logDir = Join-Path $RepoRoot "artifacts\real-model-chain\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stdout = Join-Path $logDir "admin-$Port.out.log"
$stderr = Join-Path $logDir "admin-$Port.err.log"
$process = Start-Process `
  -FilePath $JavaExe `
  -ArgumentList @(
    "-jar",
    $JarPath,
    "--server.port=$Port",
    "--agent-rag.single-tenant-id=$SingleTenantId",
    "--agent-rag.read-timeout-ms=$ReadTimeoutMs",
    "--agent-rag.total-timeout-ms=$TotalTimeoutMs"
  ) `
  -WorkingDirectory $RepoRoot `
  -WindowStyle Hidden `
  -RedirectStandardOutput $stdout `
  -RedirectStandardError $stderr `
  -PassThru

$process.Id | Set-Content -Encoding ascii (Join-Path $logDir "admin-$Port.pid")
[pscustomobject]@{
  pid = $process.Id
  port = $Port
  singleTenantId = $SingleTenantId
  readTimeoutMs = $ReadTimeoutMs
  totalTimeoutMs = $TotalTimeoutMs
  stdout = $stdout
  stderr = $stderr
}
