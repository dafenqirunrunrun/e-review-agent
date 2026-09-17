param(
  [string]$AdminBaseUrl = "http://localhost:8083",
  [string]$AdminUsername = "admin123",
  [string]$AdminPassword = "admin123"
)

$ErrorActionPreference = "Stop"

function Invoke-JsonPost {
  param([string]$Url, [hashtable]$Headers, [object]$Body = @{})
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

$local = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/tool/manifest/local" -Headers $headers
$openapi = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/tool/manifest/openapi" -Headers $headers
$mcp = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/tool/manifest/mcp-like" -Headers $headers
Assert-Ok $local "local manifest"
Assert-Ok $openapi "openapi-like manifest"
Assert-Ok $mcp "mcp-like manifest"

$openapiOperationCount = if ($openapi.data.operationCount) { $openapi.data.operationCount } else { @($openapi.data.paths.PSObject.Properties).Count }
if (($local.data.tools.Count -lt 5) -or ($openapiOperationCount -lt 5) -or ($mcp.data.tools.Count -lt 5)) {
  throw "tool manifest count is too low"
}
if ([string]$mcp.data.disclaimer -notmatch "MCP-like") {
  throw "mcp-like manifest must include local-only disclaimer"
}

$validate = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/tool/schema/validate" -Headers $headers
Assert-Ok $validate "schema validate"
if ($validate.data.invalidCount -ne 0) {
  throw "schema validation has invalid tools"
}

$contract = Invoke-JsonPost -Url "$AdminBaseUrl/admin/ai/tool/schema/test" -Headers $headers
Assert-Ok $contract "schema test"
if ($contract.data.failedCount -ne 0) {
  throw "schema contract test failed"
}

$summary = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/tool/execution/summary" -Headers $headers
$unregistered = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/tool/execution/unregistered" -Headers $headers
Assert-Ok $summary "tool execution summary"
Assert-Ok $unregistered "unregistered tool check"

[ordered]@{
  localTools = $local.data.tools.Count
  openapiOperations = $openapiOperationCount
  mcpLikeTools = $mcp.data.tools.Count
  invalidSchemaCount = $validate.data.invalidCount
  unregisteredToolCount = $unregistered.data.total
  protocolResult = "TOOL_PROTOCOL_CHECK_PASS"
  schemaResult = "TOOL_SCHEMA_CHECK_PASS"
} | ConvertTo-Json -Depth 6
