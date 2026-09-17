param(
  [string]$AdminBaseUrl = "http://localhost:8083",
  [string]$AdminUsername = "admin123",
  [string]$AdminPassword = "admin123"
)

$ErrorActionPreference = "Stop"

function Invoke-JsonPost {
  param([string]$Url, [hashtable]$Headers, [object]$Body)
  Invoke-RestMethod -Method Post -Uri $Url -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
}

function Assert-Ok {
  param([object]$Response, [string]$Name)
  if ($null -eq $Response -or $Response.errno -ne 0) {
    $message = if ($Response) { $Response.errmsg } else { "empty response" }
    throw "$Name failed: errno=$($Response.errno), errmsg=$message"
  }
}

$login = Invoke-JsonPost -Url "$AdminBaseUrl/admin/auth/login" -Headers @{} -Body @{
  username = $AdminUsername
  password = $AdminPassword
}
Assert-Ok $login "admin login"
$headers = @{ "X-Litemall-Admin-Token" = $login.data.token }

$checks = @(
  "/admin/profile/nnotice",
  "/admin/profile/lsnotice",
  "/admin/dashboard",
  "/admin/comment/list?page=1&limit=10",
  "/admin/comment/list?page=1&limit=10&userId=undefined&valueId=null",
  "/admin/ai/dashboard/summary",
  "/admin/ai/review/list?page=1&limit=10",
  "/admin/ai/review/list?page=1&limit=10&productId=undefined&sentimentLabel=null",
  "/admin/ai/demo-review/list?page=1&limit=10",
  "/admin/ai/risk/list?page=1&limit=10",
  "/admin/ai/risk/list?page=1&limit=10&riskLevel=undefined&riskType=null&status=",
  "/admin/ai/patrol/status",
  "/admin/ai/patrol/logs?page=1&limit=10",
  "/admin/ai/operation/list?page=1&limit=10",
  "/admin/ai/operation/list?page=1&limit=10&status=undefined",
  "/admin/ai/agent/run/list?page=1&limit=10",
  "/admin/ai/agent/run/list?page=1&limit=10&status=undefined&sourceType=null&triggerType=",
  "/admin/ai/agent/eval/summary",
  "/admin/ai/agent/eval/tool-stats",
  "/admin/ai/agent/eval/feedback-stats",
  "/admin/ai/agent/quality/summary",
  "/admin/ai/agent/diagnostics/summary",
  "/admin/ai/agent/diagnostics/recent-failures",
  "/admin/ai/agent/diagnostics/failure-groups",
  "/admin/ai/agent/diagnostics/health",
  "/admin/ai/agent/framework/status",
  "/admin/ai/case/list?page=1&limit=10&keyword=undefined&riskLevel=null&sentimentLabel=",
  "/admin/ai/case/retrieve?queryText=demo&productId=undefined&sourceId=null&topK=3",
  "/admin/ai/case/retrieve?query=demo&riskType=after_sales&topK=3",
  "/admin/ai/case/retrieve-v2?query=refund%20package%20damaged&riskType=after_sales_risk&strategy=hybrid&topK=3",
  "/admin/ai/case/retrieve-compare?query=refund%20package%20damaged&riskType=after_sales_risk&topK=3",
  "/admin/ai/case/retrieval/failures",
  "/admin/ai/case/retrieval/metrics",
  "/admin/ai/tool/registry/list",
  "/admin/ai/tool/registry/detail?toolName=review_text_analyzer",
  "/admin/ai/tool/manifest/local",
  "/admin/ai/tool/schema/validate",
  "/admin/ai/tool/execution/summary",
  "/admin/ai/tool/policy/list",
  "/admin/ai/tool/execution/logs?page=1&limit=10",
  "/admin/ai/tool/approval/pending",
  "/admin/ai/memory/profile/list?page=1&limit=10",
  "/admin/ai/memory/profile/detail?entityType=goods&entityId=1181000",
  "/admin/ai/guardrail/events",
  "/admin/ai/guardrail/summary",
  "/admin/ai/agentops/summary",
  "/admin/ai/agentops/trends",
  "/admin/ai/agentops/slo",
  "/admin/ai/agent/registry/list",
  "/admin/ai/agent/registry/detail?name=review_analyst",
  "/admin/ai/rag/quality/summary"
)

$results = @()
foreach ($path in $checks) {
  $url = "$AdminBaseUrl$path"
  try {
    $response = Invoke-RestMethod -Method Get -Uri $url -Headers $headers
    Assert-Ok $response $path
    $results += [ordered]@{ path = $path; status = "PASS"; errno = $response.errno }
  } catch {
    $results += [ordered]@{ path = $path; status = "FAIL"; error = $_.Exception.Message }
  }
}

try {
  $runResponse = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/agent/run/list?page=1&limit=1" -Headers $headers
  Assert-Ok $runResponse "agent run list for dynamic checks"
  $runs = @($runResponse.data.list)
  if ($runs.Count -gt 0 -and $runs[0].id) {
    $runId = $runs[0].id
    foreach ($path in @("/admin/ai/agent/run/state/$runId", "/admin/ai/agent/run/compare?leftRunId=$runId&rightRunId=$runId")) {
      try {
        $response = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl$path" -Headers $headers
        Assert-Ok $response $path
        $results += [ordered]@{ path = $path; status = "PASS"; errno = $response.errno }
      } catch {
        $results += [ordered]@{ path = $path; status = "FAIL"; error = $_.Exception.Message }
      }
    }
  } else {
    $results += [ordered]@{ path = "/admin/ai/agent/run/state/{runId}"; status = "SKIP"; reason = "no Agent Run records" }
    $results += [ordered]@{ path = "/admin/ai/agent/run/compare"; status = "SKIP"; reason = "no Agent Run records" }
  }
} catch {
  $results += [ordered]@{ path = "dynamic agent run checks"; status = "FAIL"; error = $_.Exception.Message }
}

$failed = $results | Where-Object { $_.status -eq "FAIL" }
[ordered]@{
  checks = $results
  result = if ($failed) { "FAIL" } else { "ADMIN_API_MATRIX_PASS" }
} | ConvertTo-Json -Depth 8

if ($failed) {
  exit 1
}
