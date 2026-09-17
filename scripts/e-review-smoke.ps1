param(
  [string]$AdminBaseUrl = "http://localhost:8083",
  [string]$AdminUsername = "admin123",
  [string]$AdminPassword = "admin123",
  [string]$AiServiceBaseUrl = "http://127.0.0.1:8008",
  [string]$FrontendUrl = "http://localhost:9527/#/ai-workbench/dashboard"
)

$ErrorActionPreference = "Stop"

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

Write-Host "Checking AI service health..."
$health = Invoke-RestMethod -Method Get -Uri "$AiServiceBaseUrl/api/v1/health"
if ($health.status -ne "ok") {
  throw "AI service health check failed"
}

Write-Host "Checking frontend route..."
$frontendStatus = (Invoke-WebRequest -UseBasicParsing -Uri $FrontendUrl -TimeoutSec 25).StatusCode
if ($frontendStatus -ne 200) {
  throw "Frontend route check failed with HTTP $frontendStatus"
}

Write-Host "Logging in admin API..."
$login = Invoke-JsonPost -Url "$AdminBaseUrl/admin/auth/login" -Headers @{} -Body @{
  username = $AdminUsername
  password = $AdminPassword
}
Assert-Ok $login "admin login"
$headers = @{ "X-Litemall-Admin-Token" = $login.data.token }

Write-Host "Submitting demo review..."
$demo = Invoke-JsonPost -Url "$AdminBaseUrl/admin/ai/demo-review/create" -Headers $headers -Body @{
  productId = 1006002
  productName = "E-Review Smoke Test Product"
  categoryName = "Smoke Test"
  nickname = "smoke-user"
  rating = 1
  reviewText = "Package was broken, refund requested, after-sales did not respond."
  imageUrl = "https://example.com/smoke-review.jpg"
}
Assert-Ok $demo "demo review create"

Write-Host "Running patrol once..."
$patrolRun = Invoke-JsonPost -Url "$AdminBaseUrl/admin/ai/patrol/run-once" -Headers $headers -Body @{}
Assert-Ok $patrolRun "patrol run"

Write-Host "Checking dashboard overview..."
$dashboard = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/dashboard/summary" -Headers $headers
Assert-Ok $dashboard "dashboard summary"
$overview = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/dashboard/operation-overview" -Headers $headers
Assert-Ok $overview "dashboard operation overview"

Write-Host "Checking risk and operation center..."
$riskListUrl = "{0}/admin/ai/risk/list?page=1&limit=10" -f $AdminBaseUrl
$riskList = Invoke-RestMethod -Method Get -Uri $riskListUrl -Headers $headers
Assert-Ok $riskList "risk list"
$operationListUrl = "{0}/admin/ai/operation/list?page=1&limit=10" -f $AdminBaseUrl
$operationList = Invoke-RestMethod -Method Get -Uri $operationListUrl -Headers $headers
Assert-Ok $operationList "operation list"

if ($operationList.data.total -gt 0) {
  $task = $operationList.data.list | Select-Object -First 1
  $operationDetail = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/operation/detail/$($task.id)" -Headers $headers
  Assert-Ok $operationDetail "operation detail"

  $handle = Invoke-JsonPost -Url "$AdminBaseUrl/admin/ai/operation/handle" -Headers $headers -Body @{
    riskTaskId = $task.id
    actionType = "smoke_check"
    newStatus = "viewed"
    operator = "admin"
    note = "smoke test handled"
  }
  Assert-Ok $handle "operation handle"

  $logs = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/operation/logs/$($task.id)" -Headers $headers
  Assert-Ok $logs "operation logs"
}

[ordered]@{
  aiService = "ok"
  frontend = $frontendStatus
  dashboardAnalyses = $dashboard.data.totalAnalyses
  openRiskTasks = $dashboard.data.openRiskTasks
  operationTasks = $operationList.data.total
  result = "PASS"
} | ConvertTo-Json -Depth 6
