param(
  [string]$AdminBaseUrl = "http://127.0.0.1:8083",
  [string]$AiBaseUrl = "http://127.0.0.1:8008",
  [string]$AdminUsername = $env:LITEMALL_ADMIN_USERNAME,
  [string]$AdminPassword = $env:LITEMALL_ADMIN_PASSWORD
)

$ErrorActionPreference = "Stop"

function Invoke-JsonPost {
  param([string]$Url, [hashtable]$Headers, [object]$Body)
  Invoke-RestMethod -Method Post -Uri $Url -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
}

if (-not $AdminUsername) { $AdminUsername = "admin123" }
if (-not $AdminPassword) { $AdminPassword = "admin123" }

$health = Invoke-RestMethod -Method Get -Uri "$AiBaseUrl/api/v1/health" -TimeoutSec 10
if ($health.status -ne "ok") { throw "AI health failed" }

$ready = Invoke-RestMethod -Method Get -Uri "$AiBaseUrl/api/v1/internal/agent-rag/ready" -TimeoutSec 10
if ($ready.status -notin @("ready", "degraded")) { throw "AI readiness failed: $($ready.status)" }

$login = Invoke-JsonPost -Url "$AdminBaseUrl/admin/auth/login" -Headers @{} -Body @{ username = $AdminUsername; password = $AdminPassword }
if ($login.errno -ne 0) { throw "Admin login failed: $($login.errmsg)" }
$headers = @{ "X-Litemall-Admin-Token" = $login.data.token }

$runtime = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/agent-rag/health" -Headers $headers -TimeoutSec 10
if ($runtime.errno -ne 0) { throw "Agent-RAG runtime health failed" }

$payload = @{
  requestId = "local-smoke-$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
  tenantId = "__local__"
  subjectType = "review"
  subjectId = "local-smoke-review"
  query = "Package is broken and asks for refund. Please check after-sales risk."
  runtimeMode = "local-model"
  schemaVersion = "2.0.0"
  retrieval = @{ enabled = $true; topK = 5; rerankTopK = 3; publicTenantEnabled = $true }
  context = @{ syntheticFixture = $true }
}
$analyze = Invoke-JsonPost -Url "$AdminBaseUrl/admin/agent-rag/analyze" -Headers $headers -Body $payload
if ($analyze.errno -ne 0) { throw "Agent-RAG analyze failed: $($analyze.errmsg)" }

[ordered]@{
  aiHealth = $health.status
  aiReady = $ready.status
  runtimeStatus = $runtime.data.runtime.status
  runId = $analyze.data.id
  result = "PASS"
} | ConvertTo-Json -Depth 6
Write-Host "E_REVIEW_LOCAL_SMOKE_PASS"
