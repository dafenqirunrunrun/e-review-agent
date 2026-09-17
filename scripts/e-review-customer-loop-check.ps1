param(
  [string]$UserFrontendUrl = "http://localhost:6255",
  [string]$WxBaseUrl = "http://localhost:8080",
  [string]$AdminFrontendUrl = "http://localhost:9527",
  [string]$AdminBaseUrl = "http://localhost:8083",
  [string]$AiServiceBaseUrl = "http://127.0.0.1:8008",
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$MysqlDatabase = "litemall",
  [string]$AdminUsername = "admin123",
  [string]$AdminPassword = "admin123"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "e-review-db-common.ps1")
$db = Get-EReviewDbConfig -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase
$MysqlUser = $db.User
$MysqlPassword = $db.Password
$MysqlDatabase = $db.Database

function Assert-Ok {
  param(
    [object]$Response,
    [string]$Name
  )
  if ($null -eq $Response -or $Response.errno -ne 0) {
    $message = if ($Response) { $Response.errmsg } else { "empty response" }
    throw "$Name failed: $message"
  }
}

function Invoke-JsonPost {
  param(
    [string]$Url,
    [hashtable]$Headers,
    [object]$Body
  )
  Invoke-RestMethod -Method Post -Uri $Url -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
}

Write-Host "Checking H5 user frontend..."
$userFrontendStatus = (Invoke-WebRequest -UseBasicParsing -Uri $UserFrontendUrl -TimeoutSec 25).StatusCode
if ($userFrontendStatus -ne 200) {
  throw "H5 user frontend check failed with HTTP $userFrontendStatus"
}

Write-Host "Checking wx-api home..."
$wxHome = Invoke-RestMethod -Method Get -Uri "$WxBaseUrl/wx/home/index"
Assert-Ok $wxHome "wx home"

Write-Host "Checking admin frontend..."
$adminFrontendStatus = (Invoke-WebRequest -UseBasicParsing -Uri $AdminFrontendUrl -TimeoutSec 25).StatusCode
if ($adminFrontendStatus -ne 200) {
  throw "Admin frontend check failed with HTTP $adminFrontendStatus"
}

Write-Host "Checking AI service health..."
$health = Invoke-RestMethod -Method Get -Uri "$AiServiceBaseUrl/api/v1/health"
if ($health.status -ne "ok") {
  throw "AI service health check failed"
}

Write-Host "Checking admin dashboard..."
$login = Invoke-JsonPost -Url "$AdminBaseUrl/admin/auth/login" -Headers @{} -Body @{
  username = $AdminUsername
  password = $AdminPassword
}
Assert-Ok $login "admin login"
$headers = @{ "X-Litemall-Admin-Token" = $login.data.token }
$dashboard = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/dashboard/summary" -Headers $headers
Assert-Ok $dashboard "dashboard summary"
$riskList = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/risk/list?page=1&limit=1" -Headers $headers
Assert-Ok $riskList "risk list"
$agentFramework = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/agent/framework/status" -Headers $headers
Assert-Ok $agentFramework "agent framework status"

Write-Host "Seeding stable customer demo products..."
$seedScript = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "seed-demo-products.ps1"
if (Test-Path $seedScript) {
  powershell -ExecutionPolicy Bypass -File $seedScript -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase | Write-Host
}

Write-Host "Checking litemall_comment source analysis records..."
$previous = $env:MYSQL_PWD
try {
  $env:MYSQL_PWD = $MysqlPassword
  $analysisCountText = mysql "-u$MysqlUser" -N -D $MysqlDatabase -e "select count(1) from litemall_review_ai_analysis where source_type='litemall_comment' and deleted=0;"
  if ($LASTEXITCODE -ne 0) {
    throw "mysql source_type check failed"
  }
} finally {
  $env:MYSQL_PWD = $previous
}
$analysisCount = [int](($analysisCountText | Select-Object -Last 1).Trim())
if ($analysisCount -le 0) {
  throw "No source_type=litemall_comment analysis record found"
}

[ordered]@{
  userFrontend = $userFrontendStatus
  wxApi = "ok"
  adminFrontend = $adminFrontendStatus
  adminApi = "ok"
  aiService = "ok"
  dashboardAnalyses = $dashboard.data.totalAnalyses
  riskTasks = $riskList.data.total
  agentFrameworkMode = $agentFramework.data.current_mode
  litemallCommentAnalyses = $analysisCount
  result = "PASS"
} | ConvertTo-Json -Depth 6
