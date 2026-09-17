param(
  [string]$AdminBaseUrl = "http://localhost:8083",
  [string]$WxBaseUrl = "http://localhost:8080",
  [string]$AdminUsername = "admin123",
  [string]$AdminPassword = "admin123"
)

$ErrorActionPreference = "Stop"

function Invoke-JsonPost {
  param(
    [string]$Url,
    [hashtable]$Headers,
    [object]$Body
  )
  Invoke-RestMethod -Method Post -Uri $Url -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
}

function Assert-Ok {
  param([object]$Response, [string]$Name)
  if ($null -eq $Response -or $Response.errno -ne 0) {
    $message = if ($Response) { $Response.errmsg } else { "empty response" }
    throw "$Name failed: $message"
  }
}

$login = Invoke-JsonPost -Url "$AdminBaseUrl/admin/auth/login" -Headers @{} -Body @{
  username = $AdminUsername
  password = $AdminPassword
}
Assert-Ok $login "admin login"
$headers = @{ "X-Litemall-Admin-Token" = $login.data.token }

$adminStatus = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/demo/status" -Headers $headers
Assert-Ok $adminStatus "admin demo status"

$wxStatus = Invoke-RestMethod -Method Get -Uri "$WxBaseUrl/wx/ai-demo/status"
Assert-Ok $wxStatus "wx demo status"

if ($adminStatus.data.demoModeEnabled -ne $true -or $wxStatus.data.demoModeEnabled -ne $true) {
  throw "demo mode is not enabled"
}
if ($adminStatus.data.demoPaymentEnabled -ne $true -or $wxStatus.data.demoPaymentEnabled -ne $true) {
  throw "demo payment is not enabled"
}
if ($adminStatus.data.demoShippingEnabled -ne $true -or $wxStatus.data.demoShippingEnabled -ne $true) {
  throw "demo shipping is not enabled"
}

$messageFields = @(
  $adminStatus.data.message,
  $adminStatus.data.boundary,
  $wxStatus.data.paymentNotice,
  $wxStatus.data.shippingNotice
)
foreach ($field in $messageFields) {
  if (-not $field -or $field.Length -lt 6) {
    throw "demo status message field is missing"
  }
}

[ordered]@{
  adminDemoMode = $adminStatus.data.demoModeEnabled
  wxDemoMode = $wxStatus.data.demoModeEnabled
  mainProductId = $adminStatus.data.mainProductId
  result = "DEMO_MODE_CHECK_PASS"
} | ConvertTo-Json -Depth 4
