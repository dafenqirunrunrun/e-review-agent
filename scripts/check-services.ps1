param(
  [string]$UserFrontendUrl = "http://localhost:6255",
  [string]$WxHomeUrl = "http://localhost:8080/wx/home/index",
  [string]$AdminFrontendUrl = "http://localhost:9527",
  [string]$AdminBaseUrl = "http://localhost:8083",
  [string]$AiHealthUrl = "http://127.0.0.1:8008/api/v1/health",
  [string]$AdminUsername = "admin123",
  [string]$AdminPassword = "admin123"
)

$ErrorActionPreference = "Stop"

function Test-Port {
  param([int]$Port)
  $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($connection) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)" -ErrorAction SilentlyContinue
    $startTime = $null
    $path = $null
    $commandLine = $null
    if ($process) {
      $startTime = $process.CreationDate
      $path = $process.ExecutablePath
      $commandLine = $process.CommandLine
    }
    return [ordered]@{
      port = $Port
      listening = $true
      processId = $connection.OwningProcess
      startTime = $startTime
      executablePath = $path
      jarPath = if ($commandLine -match '([A-Za-z]:\\[^"]+?\.jar)') { $Matches[1] } else { $null }
    }
  }
  return [ordered]@{ port = $Port; listening = $false; processId = $null; startTime = $null; executablePath = $null; jarPath = $null }
}

function Invoke-JsonPost {
  param(
    [string]$Url,
    [hashtable]$Headers,
    [object]$Body
  )
  Invoke-RestMethod -Method Post -Uri $Url -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
}

$ports = @(8008, 8080, 8083, 6255, 9527) | ForEach-Object { Test-Port -Port $_ }

$http = [ordered]@{}
$http.userFrontend = (Invoke-WebRequest -UseBasicParsing -Uri $UserFrontendUrl -TimeoutSec 25).StatusCode
$wxHome = Invoke-RestMethod -Method Get -Uri $WxHomeUrl
$http.wxApi = if ($wxHome.errno -eq 0) { "ok" } else { "error: $($wxHome.errmsg)" }
$http.adminFrontend = (Invoke-WebRequest -UseBasicParsing -Uri $AdminFrontendUrl -TimeoutSec 25).StatusCode
$health = Invoke-RestMethod -Method Get -Uri $AiHealthUrl
$http.aiHealth = $health.status

$login = Invoke-JsonPost -Url "$AdminBaseUrl/admin/auth/login" -Headers @{} -Body @{
  username = $AdminUsername
  password = $AdminPassword
}
if ($login.errno -ne 0) {
  throw "admin login failed: $($login.errmsg)"
}

$headers = @{ "X-Litemall-Admin-Token" = $login.data.token }
$dashboard = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/dashboard/summary" -Headers $headers
if ($dashboard.errno -ne 0) {
  throw "dashboard summary failed: $($dashboard.errmsg)"
}
$adminNotice = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/profile/nnotice" -Headers $headers
if ($adminNotice.errno -ne 0) {
  throw "admin profile notice failed: $($adminNotice.errmsg)"
}
$adminDashboard = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/dashboard" -Headers $headers
if ($adminDashboard.errno -ne 0) {
  throw "admin dashboard failed: $($adminDashboard.errmsg)"
}
$agentEval = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/agent/eval/summary" -Headers $headers
if ($agentEval.errno -ne 0) {
  throw "agent eval summary failed: $($agentEval.errmsg)"
}
$agentFramework = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/agent/framework/status" -Headers $headers
if ($agentFramework.errno -ne 0) {
  throw "agent framework status failed: $($agentFramework.errmsg)"
}
$riskList = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/risk/list?page=1&limit=1" -Headers $headers
if ($riskList.errno -ne 0) {
  throw "risk list failed: $($riskList.errmsg)"
}

[ordered]@{
  ports = $ports
  http = $http
  dashboardAnalyses = $dashboard.data.totalAnalyses
  openRiskTasks = $dashboard.data.openRiskTasks
  riskTasks = $riskList.data.total
  adminApiChecks = [ordered]@{
    profileNotice = "ok"
    dashboard = "ok"
    agentEval = "ok"
    agentFramework = $agentFramework.data.current_mode
  }
  result = "PASS"
} | ConvertTo-Json -Depth 8
