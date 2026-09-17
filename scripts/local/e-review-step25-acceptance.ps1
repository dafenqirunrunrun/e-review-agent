param(
  [string]$RuntimeHome = $env:E_REVIEW_RUNTIME_HOME,
  [string]$AdminBaseUrl = "http://127.0.0.1:8083",
  [string]$AiBaseUrl = "http://127.0.0.1:8008",
  [string]$FrontendUrl = "http://127.0.0.1:9527",
  [string]$AdminUsername = $env:LITEMALL_ADMIN_USERNAME,
  [string]$AdminPassword = $env:LITEMALL_ADMIN_PASSWORD
)

$ErrorActionPreference = "Stop"

function Resolve-RuntimeHome {
  param([string]$Configured)
  if ($Configured) { return $Configured }
  if ($env:LOCALAPPDATA) { return (Join-Path $env:LOCALAPPDATA "EReviewAgent\runtime") }
  return (Join-Path $HOME ".e-review-agent\runtime")
}

function Assert-True {
  param([bool]$Condition, [string]$Code)
  if (-not $Condition) { throw $Code }
}

function Invoke-JsonPost {
  param([string]$Url, [hashtable]$Headers = @{}, [object]$Body)
  Invoke-RestMethod -Method Post -Uri $Url -Headers $Headers -ContentType "application/json" `
    -Body ($Body | ConvertTo-Json -Depth 10) -TimeoutSec 65
}

if (-not $AdminUsername) { $AdminUsername = "admin123" }
if (-not $AdminPassword) { $AdminPassword = "admin123" }

$root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..\..")).Path
$runtime = Resolve-RuntimeHome $RuntimeHome
$statusDir = Join-Path $runtime "status"
New-Item -ItemType Directory -Force -Path $statusDir | Out-Null

$runtimeStatusText = powershell -NoProfile -ExecutionPolicy Bypass -File `
  (Join-Path $root "scripts\local\e-review-status.ps1") -RuntimeHome $runtime -Json | Out-String
if ($LASTEXITCODE -ne 0) { throw "STEP25_RUNTIME_STATUS_FAILED" }
$runtimeStatus = $runtimeStatusText | ConvertFrom-Json
Assert-True ($runtimeStatus.status -eq "PASS") "STEP25_RUNTIME_NOT_READY"

$frontend = Invoke-WebRequest -UseBasicParsing -Uri $FrontendUrl -TimeoutSec 15
$health = Invoke-RestMethod -Uri "$AiBaseUrl/api/v1/health" -TimeoutSec 15
$liveness = Invoke-RestMethod -Uri "$AiBaseUrl/api/v1/system/liveness" -TimeoutSec 15
$readiness = Invoke-RestMethod -Uri "$AiBaseUrl/api/v1/system/readiness" -TimeoutSec 30
Assert-True ($frontend.StatusCode -eq 200) "STEP25_FRONTEND_UNAVAILABLE"
Assert-True ($health.status -eq "ok") "STEP25_AI_HEALTH_FAILED"
Assert-True ($liveness.status -eq "ok") "STEP25_AI_LIVENESS_FAILED"
Assert-True ($readiness.status -in @("ready", "degraded")) "STEP25_AI_READINESS_FAILED"

$login = Invoke-JsonPost -Url "$AdminBaseUrl/admin/auth/login" -Body @{
  username = $AdminUsername
  password = $AdminPassword
}
Assert-True ($login.errno -eq 0) "STEP25_ADMIN_LOGIN_FAILED"
$headers = @{ "X-Litemall-Admin-Token" = $login.data.token }

$indexBefore = (Invoke-RestMethod -Uri "$AdminBaseUrl/admin/ai/documents/index/status" -Headers $headers -TimeoutSec 15).data
Assert-True ($indexBefore.runtime.reloadStatus -eq "ready") "STEP25_INDEX_RUNTIME_NOT_READY"
$loadedBefore = $indexBefore.runtime.loadedIndexVersion

$normal = (Invoke-JsonPost -Url "$AdminBaseUrl/admin/ai/review/policy-playground/query" -Headers $headers -Body @{
  query = "hello"
  mode = "evidence_search"
  topK = 3
  indexTarget = "current"
}).data
Assert-True ($normal.decision.code -eq "input_guidance") "STEP25_NORMAL_INPUT_DECISION_INVALID"
Assert-True (@($normal.riskTypes).Count -eq 0) "STEP25_NORMAL_INPUT_FALSE_RISK"
Assert-True (@($normal.evidence).Count -eq 0) "STEP25_NORMAL_INPUT_FALSE_EVIDENCE"
Assert-True (-not $normal.requiresHumanReview) "STEP25_NORMAL_INPUT_FALSE_HUMAN_REVIEW"

$riskQuery = "The merchant requires a five-star screenshot for cashback and threatens to delete negative reviews."
$current = (Invoke-JsonPost -Url "$AdminBaseUrl/admin/ai/review/policy-playground/query" -Headers $headers -Body @{
  query = $riskQuery
  mode = "evidence_search"
  topK = 3
  indexTarget = "current"
}).data
Assert-True ($current.evidenceStatus -eq "supported") "STEP25_CURRENT_EVIDENCE_NOT_SUPPORTED"
Assert-True (@($current.evidence).Count -gt 0) "STEP25_CURRENT_EVIDENCE_EMPTY"
Assert-True (@($current.evidence | Where-Object { $_.sourceUrl -match '^https?://' -and $_.contentHash }).Count -gt 0) "STEP25_CURRENT_CITATION_INVALID"

$comparison = $null
if ($indexBefore.comparableRelease) {
  $comparison = (Invoke-JsonPost -Url "$AdminBaseUrl/admin/ai/review/policy-playground/query" -Headers $headers -Body @{
    query = $riskQuery
    mode = "evidence_search"
    topK = 3
    indexTarget = "candidate"
    candidateVersion = $indexBefore.comparableRelease.version
  }).data
  Assert-True ($comparison.evidenceStatus -eq "supported") "STEP25_COMPARABLE_EVIDENCE_NOT_SUPPORTED"
  Assert-True (@($comparison.evidence).Count -gt 0) "STEP25_COMPARABLE_EVIDENCE_EMPTY"
}

$workflow = Invoke-JsonPost -Url "$AiBaseUrl/api/v1/review/analyze" -Body @{
  reviewId = "step25-isolated-$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
  productId = "1006002"
  productName = "Step 25 isolated fixture"
  reviewText = $riskQuery
  imageUrls = @()
  rating = 5
  ratingSource = "USER_PROVIDED"
}
$governance = $workflow.review_governance
Assert-True ($governance.decision.code -ne "auto_pass") "STEP25_HIGH_RISK_AUTO_PASS"
Assert-True ($governance.evidenceStatus -eq "supported") "STEP25_WORKFLOW_EVIDENCE_NOT_SUPPORTED"
Assert-True ($governance.requiresHumanReview) "STEP25_HIGH_RISK_NOT_ROUTED_TO_HUMAN"
$nodes = @($workflow.workflow_trace | ForEach-Object { $_.node })
foreach ($requiredNode in @("intent_router", "planner", "execution", "reflection", "finalize")) {
  Assert-True ($nodes -contains $requiredNode) "STEP25_WORKFLOW_NODE_MISSING_$requiredNode"
}

$indexAfter = (Invoke-RestMethod -Uri "$AdminBaseUrl/admin/ai/documents/index/status" -Headers $headers -TimeoutSec 15).data
Assert-True ($indexAfter.runtime.loadedIndexVersion -eq $loadedBefore) "STEP25_READ_ONLY_CHECK_CHANGED_RUNTIME_INDEX"

$result = [ordered]@{
  schemaVersion = "step25-final-acceptance-v1"
  generatedAt = (Get-Date).ToString("o")
  gate = "PASS"
  runtime = [ordered]@{
    services = $runtimeStatus.services
    workers = $runtimeStatus.workers
    aiReadiness = $readiness.status
  }
  normalInput = [ordered]@{
    decision = $normal.decision.code
    riskCount = @($normal.riskTypes).Count
    evidenceCount = @($normal.evidence).Count
    requiresHumanReview = [bool]$normal.requiresHumanReview
  }
  riskEvidence = [ordered]@{
    evidenceStatus = $current.evidenceStatus
    riskTypes = @($current.riskTypes)
    citationCount = @($current.evidence).Count
    actualMode = $current.technical.actualMode
  }
  comparison = [ordered]@{
    executed = [bool]$comparison
    version = if ($indexBefore.comparableRelease) { $indexBefore.comparableRelease.version } else { $null }
    evidenceStatus = if ($comparison) { $comparison.evidenceStatus } else { $null }
    actualMode = if ($comparison) { $comparison.technical.actualMode } else { $null }
  }
  workflow = [ordered]@{
    decision = $governance.decision.code
    evidenceStatus = $governance.evidenceStatus
    requiresHumanReview = [bool]$governance.requiresHumanReview
    riskTypes = @($governance.riskTypes)
    nodes = $nodes
  }
  indexIsolation = [ordered]@{
    before = $loadedBefore
    after = $indexAfter.runtime.loadedIndexVersion
    unchanged = $true
  }
}

$output = Join-Path $statusDir "step25-acceptance.json"
$result | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $output
$result | ConvertTo-Json -Depth 10
Write-Host "STEP25_ACCEPTANCE_GATE=PASS"
