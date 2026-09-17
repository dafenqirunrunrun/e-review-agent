param(
  [string]$AdminBaseUrl = "http://localhost:8083",
  [string]$AiServiceBaseUrl = "http://127.0.0.1:8008",
  [string]$AdminUsername = "admin123",
  [string]$AdminPassword = "admin123"
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
  Invoke-RestMethod -Method Post -Uri $Url -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 10)
}

Write-Host "Checking AI health..."
$health = Invoke-RestMethod -Method Get -Uri "$AiServiceBaseUrl/api/v1/health"
if ($health.status -ne "ok") {
  throw "AI service health failed"
}

Write-Host "Checking agent framework status..."
$frameworkStatus = Invoke-RestMethod -Method Get -Uri "$AiServiceBaseUrl/api/v1/agent-framework/status"

Write-Host "Checking agent framework analyze..."
$payload = @{
  review_id = "agent-framework-check"
  product_id = "1006002"
  product_name = "E-Review Agent Demo Product"
  category = "demo"
  rating = 1
  review_text = "The picture looks fine, but the real product is broken and I need after-sales support."
  image_urls = @("https://example.com/broken-product.jpg")
}
$analysis = Invoke-JsonPost -Url "$AiServiceBaseUrl/api/v1/agent-framework/analyze" -Headers @{} -Body $payload
if (-not $analysis.workflow_trace -or $analysis.workflow_trace.Count -lt 9) {
  throw "agent framework analyze did not return enough workflow trace nodes"
}
if (-not $analysis.modality_conflict -or -not $analysis.dominant_modality) {
  throw "agent framework analyze missing modality outputs"
}

Write-Host "Checking admin agent APIs..."
$login = Invoke-JsonPost -Url "$AdminBaseUrl/admin/auth/login" -Headers @{} -Body @{
  username = $AdminUsername
  password = $AdminPassword
}
Assert-Ok $login "admin login"
$headers = @{ "X-Litemall-Admin-Token" = $login.data.token }

$adminFramework = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/agent/framework/status" -Headers $headers
Assert-Ok $adminFramework "admin framework status"
$runList = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/agent/run/list?page=1&limit=1" -Headers $headers
Assert-Ok $runList "agent run list"
$evalSummary = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/agent/eval/summary" -Headers $headers
Assert-Ok $evalSummary "agent eval summary"
$toolStats = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/agent/eval/tool-stats" -Headers $headers
Assert-Ok $toolStats "agent tool stats"
$feedbackStats = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/agent/eval/feedback-stats" -Headers $headers
Assert-Ok $feedbackStats "agent feedback stats"

[ordered]@{
  aiHealth = "ok"
  frameworkMode = $frameworkStatus.current_mode
  frameworkFallbackEnabled = $frameworkStatus.fallback_enabled
  workflowTraceCount = $analysis.workflow_trace.Count
  sentiment = $analysis.sentiment_label
  riskLevel = $analysis.risk_level
  adminFrameworkMode = $adminFramework.data.current_mode
  runList = "ok"
  evalSummary = "ok"
  toolStats = "ok"
  feedbackStats = "ok"
  result = "PASS"
} | ConvertTo-Json -Depth 8
