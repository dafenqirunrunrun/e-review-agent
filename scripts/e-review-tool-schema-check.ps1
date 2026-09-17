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

$validate = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/tool/schema/validate" -Headers $headers
Assert-Ok $validate "schema validate"
if ($validate.data.invalidCount -ne 0) {
  [ordered]@{
    result = "TOOL_SCHEMA_CHECK_FAIL"
    invalidTools = $validate.data.invalidTools
  } | ConvertTo-Json -Depth 8
  exit 1
}

$contract = Invoke-JsonPost -Url "$AdminBaseUrl/admin/ai/tool/schema/test" -Headers $headers
Assert-Ok $contract "schema contract test"
if ($contract.data.failedCount -ne 0) {
  [ordered]@{
    result = "TOOL_SCHEMA_CHECK_FAIL"
    contractTests = $contract.data.contractTests
  } | ConvertTo-Json -Depth 8
  exit 1
}

$report = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/tool/schema/report" -Headers $headers
Assert-Ok $report "schema report"

[ordered]@{
  totalTools = $validate.data.totalTools
  validCount = $validate.data.validCount
  contractPassed = $contract.data.passedCount
  result = "TOOL_SCHEMA_CHECK_PASS"
} | ConvertTo-Json -Depth 6
