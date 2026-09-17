param(
  [string]$AdminBaseUrl = "http://localhost:8083",
  [string]$AdminUsername = "admin123",
  [string]$AdminPassword = "admin123"
)

$ErrorActionPreference = "Stop"

function Invoke-JsonPost {
  param([string]$Url, [hashtable]$Headers, [object]$Body)
  Invoke-RestMethod -Method Post -Uri $Url -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 10)
}

function Assert-Ok {
  param([object]$Response, [string]$Name)
  if ($null -eq $Response -or $Response.errno -ne 0) {
    throw "$Name failed"
  }
}

$login = Invoke-JsonPost -Url "$AdminBaseUrl/admin/auth/login" -Headers @{} -Body @{
  username = $AdminUsername
  password = $AdminPassword
}
Assert-Ok $login "admin login"
$headers = @{ "X-Litemall-Admin-Token" = $login.data.token }

$paths = @(
  "/admin/ai/agentops/trends?range=7d",
  "/admin/ai/agentops/recent-runs?limit=20",
  "/admin/ai/agentops/failure-top",
  "/admin/ai/agentops/tool-failure-top",
  "/admin/ai/agentops/fallback-distribution",
  "/admin/ai/agentops/guardrail-trend",
  "/admin/ai/agentops/rag-trend",
  "/admin/ai/agentops/quality-trend"
)

$checks = @()
foreach ($path in $paths) {
  $response = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl$path" -Headers $headers
  Assert-Ok $response $path
  $checks += [ordered]@{
    path = $path
    status = "PASS"
  }
}

[ordered]@{
  checks = $checks
  result = "AGENTOPS_TREND_CHECK_PASS"
} | ConvertTo-Json -Depth 8
