param(
  [string]$Root = "",
  [int]$StartupDelaySeconds = 5,
  [switch]$BuildBeforeStart
)

$ErrorActionPreference = "Stop"

function Resolve-EReviewLayout {
  param([string]$ConfiguredRoot)

  if ($ConfiguredRoot -and $ConfiguredRoot.Trim().Length -gt 0) {
    $rootPath = (Resolve-Path $ConfiguredRoot).Path
  } else {
    $scriptDir = Split-Path -Parent $MyInvocation.ScriptName
    $rootPath = (Resolve-Path (Join-Path $scriptDir "..")).Path
  }

  if (Test-Path (Join-Path $rootPath "litemall-admin-api")) {
    return [ordered]@{
      Root = $rootPath
      Litemall = $rootPath
      AiService = Join-Path $rootPath "ai-service"
    }
  }

  return [ordered]@{
    Root = $rootPath
    Litemall = Join-Path $rootPath "litemall"
    AiService = Join-Path $rootPath "ai-service"
  }
}

function Stop-PortIfListening {
  param([int]$Port)

  $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if (-not $connections) {
    Write-Host "Port $Port is free."
    return
  }

  $processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($processId in $processIds) {
    try {
      $process = Get-Process -Id $processId -ErrorAction Stop
      Write-Host "Stopping stale process on port ${Port}: PID $processId ($($process.ProcessName))"
      Stop-Process -Id $processId -Force
    } catch {
      Write-Warning "Failed to stop PID $processId on port ${Port}: $($_.Exception.Message)"
    }
  }
}

function Start-EReviewService {
  param(
    [string]$Name,
    [string]$WorkingDirectory,
    [string]$Command,
    [int]$Port = 0
  )

  Write-Host "Starting $Name..."
  $process = Start-Process -FilePath "powershell.exe" `
    -WorkingDirectory $WorkingDirectory `
    -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $Command) `
    -WindowStyle Hidden `
    -PassThru
  Write-Host "Started $Name. PID=$($process.Id), Port=$Port, WorkingDirectory=$WorkingDirectory"
  Start-Sleep -Seconds $StartupDelaySeconds
}

function Invoke-JsonPost {
  param(
    [string]$Url,
    [hashtable]$Headers,
    [object]$Body
  )
  Invoke-RestMethod -Method Post -Uri $Url -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
}

function Test-AdminApiReadiness {
  param([string]$AdminBaseUrl = "http://localhost:8083")

  $lastError = $null
  for ($attempt = 1; $attempt -le 12; $attempt++) {
    try {
      $login = Invoke-JsonPost -Url "$AdminBaseUrl/admin/auth/login" -Headers @{} -Body @{
        username = "admin123"
        password = "admin123"
      }
      if ($login.errno -ne 0) {
        throw "admin login failed after start: $($login.errmsg)"
      }

      $headers = @{ "X-Litemall-Admin-Token" = $login.data.token }
      $checks = @(
        "/admin/profile/nnotice",
        "/admin/dashboard",
        "/admin/ai/agent/eval/summary",
        "/admin/ai/agent/framework/status"
      )
      foreach ($path in $checks) {
        $result = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl$path" -Headers $headers
        if ($result.errno -ne 0) {
          throw "admin-api readiness check failed: $path errno=$($result.errno), errmsg=$($result.errmsg)"
        }
      }
      Write-Host "admin-api readiness checks passed."
      return
    } catch {
      $lastError = $_.Exception.Message
      Write-Host "Waiting for admin-api readiness... attempt $attempt/12"
      Start-Sleep -Seconds 5
    }
  }
  throw "admin-api readiness checks failed: $lastError"
}

function Test-AiServiceReadiness {
  param([string]$AiServiceBaseUrl = "http://127.0.0.1:8008")

  $lastError = $null
  for ($attempt = 1; $attempt -le 12; $attempt++) {
    try {
      $health = Invoke-RestMethod -Method Get -Uri "$AiServiceBaseUrl/api/v1/health"
      if ($health.status -ne "ok") {
        throw "AI health status is $($health.status)"
      }
      $framework = Invoke-RestMethod -Method Get -Uri "$AiServiceBaseUrl/api/v1/agent-framework/status"
      if (-not $framework.current_mode) {
        throw "AI framework status missing current_mode"
      }
      Write-Host "AI service readiness checks passed. framework_mode=$($framework.current_mode)"
      return
    } catch {
      $lastError = $_.Exception.Message
      Write-Host "Waiting for AI service readiness... attempt $attempt/12"
      Start-Sleep -Seconds 3
    }
  }
  throw "AI service readiness checks failed: $lastError"
}

$layout = Resolve-EReviewLayout -ConfiguredRoot $Root
$Root = $layout.Root
$aiDir = $layout.AiService
$litemallDir = $layout.Litemall
$wxJar = Join-Path $litemallDir "litemall-wx-api\target\litemall-wx-api-0.1.0-exec.jar"
$adminJar = Join-Path $litemallDir "litemall-admin-api\target\litemall-admin-api-0.1.0-exec.jar"
$vueDir = Join-Path $litemallDir "litemall-vue"
$adminDir = Join-Path $litemallDir "litemall-admin"

if (-not (Test-Path $aiDir)) { throw "AI service directory not found: $aiDir" }
Write-Host "Resolved E-Review Agent root: $Root"
Write-Host "Resolved litemall directory: $litemallDir"
Write-Host "Resolved AI service directory: $aiDir"
if ($BuildBeforeStart) {
  Write-Host "BuildBeforeStart enabled. Running Maven package..."
  Push-Location $litemallDir
  try {
    mvn -DskipTests package
  } finally {
    Pop-Location
  }
}
if (-not (Test-Path $wxJar)) { throw "wx-api jar not found. Run mvn -DskipTests package first: $wxJar" }
if (-not (Test-Path $adminJar)) { throw "admin-api jar not found. Run mvn -DskipTests package first: $adminJar" }
if (-not (Test-Path $vueDir)) { throw "litemall-vue directory not found: $vueDir" }
if (-not (Test-Path $adminDir)) { throw "litemall-admin directory not found: $adminDir" }

@(8008, 8080, 8083, 6255, 9527) | ForEach-Object { Stop-PortIfListening -Port $_ }
Start-Sleep -Seconds 2

Start-EReviewService -Name "AI service" -WorkingDirectory $aiDir -Command "`$env:AGENT_FRAMEWORK_ENABLED='true'; `$env:AGENT_FRAMEWORK_FALLBACK_ENABLED='true'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8008" -Port 8008
Test-AiServiceReadiness
Start-EReviewService -Name "wx-api" -WorkingDirectory $litemallDir -Command "java -jar `"$wxJar`" --server.port=8080" -Port 8080
Start-EReviewService -Name "admin-api" -WorkingDirectory $litemallDir -Command "java -jar `"$adminJar`" --server.port=8083" -Port 8083
Test-AdminApiReadiness
Start-EReviewService -Name "litemall-vue" -WorkingDirectory $vueDir -Command "npm run dev" -Port 6255
Start-EReviewService -Name "litemall-admin" -WorkingDirectory $adminDir -Command "npm run dev" -Port 9527

Write-Host "All services have been started. Run scripts\check-services.ps1 to verify readiness."
