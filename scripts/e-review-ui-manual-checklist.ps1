param(
  [string]$UserFrontendUrl = "http://localhost:6255",
  [string]$AdminFrontendUrl = "http://localhost:9527",
  [string]$WxHomeUrl = "http://localhost:8080/wx/home/index",
  [string]$AdminBaseUrl = "http://localhost:8083",
  [string]$AiHealthUrl = "http://127.0.0.1:8008/api/v1/health"
)

$ErrorActionPreference = "Stop"

Write-Host "E-Review Agent v1.0.1 manual UI checklist"
Write-Host ""
Write-Host "Customer side:"
Write-Host "  [ ] Open $UserFrontendUrl"
Write-Host "  [ ] Login with user123 / user123"
Write-Host "  [ ] Open demo product 1181000, 1006007, or 1006013"
Write-Host "  [ ] Buy now, submit order, click demo payment, click demo shipping"
Write-Host "  [ ] Confirm receipt and submit a text/image-URL review"
Write-Host ""
Write-Host "Admin side:"
Write-Host "  [ ] Open $AdminFrontendUrl"
Write-Host "  [ ] Login with admin123 / admin123"
Write-Host "  [ ] Dashboard, product comments, AI review analysis"
Write-Host "  [ ] Agent patrol, risk center, operation center"
Write-Host "  [ ] Agent Run Trace, Agent Eval, AI Agent Config"
Write-Host "  [ ] Confirm no parameter error, internal error, UTF-8 BOM, white screen, undefined/null/NaN"
Write-Host ""

$userStatus = (Invoke-WebRequest -UseBasicParsing -Uri $UserFrontendUrl -TimeoutSec 20).StatusCode
$adminStatus = (Invoke-WebRequest -UseBasicParsing -Uri $AdminFrontendUrl -TimeoutSec 20).StatusCode
$wxHome = Invoke-RestMethod -Method Get -Uri $WxHomeUrl
$aiHealth = Invoke-RestMethod -Method Get -Uri $AiHealthUrl
$adminLogin = Invoke-RestMethod -Method Post -Uri "$AdminBaseUrl/admin/auth/login" -ContentType "application/json" -Body (@{ username = "admin123"; password = "admin123" } | ConvertTo-Json)
$headers = @{ "X-Litemall-Admin-Token" = $adminLogin.data.token }
$matrix = powershell -ExecutionPolicy Bypass -File (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "e-review-admin-api-matrix-check.ps1") -AdminBaseUrl $AdminBaseUrl

[ordered]@{
  userFrontend = $userStatus
  adminFrontend = $adminStatus
  wxApi = $wxHome.errno
  aiHealth = $aiHealth.status
  adminLogin = $adminLogin.errno
  adminApiMatrix = ($matrix | Out-String).Trim()
  result = "UI_MANUAL_CHECKLIST_READY"
} | ConvertTo-Json -Depth 6

