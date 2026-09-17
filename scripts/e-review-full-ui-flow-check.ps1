param(
  [string]$UserFrontendUrl = "http://localhost:6255",
  [string]$AdminFrontendUrl = "http://localhost:9527",
  [string]$WxBaseUrl = "http://localhost:8080",
  [string]$AdminBaseUrl = "http://localhost:8083",
  [string]$AiServiceBaseUrl = "http://127.0.0.1:8008",
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$MysqlDatabase = "litemall",
  [int]$GoodsId = 1181000,
  [string]$CustomerUsername = "user123",
  [string]$CustomerPassword = "user123",
  [string]$AdminUsername = "admin123",
  [string]$AdminPassword = "admin123"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDir "e-review-db-common.ps1")
$db = Get-EReviewDbConfig -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase
$MysqlUser = $db.User
$MysqlPassword = $db.Password
$MysqlDatabase = $db.Database

function Invoke-JsonPost {
  param([string]$Url, [hashtable]$Headers, [object]$Body)
  Invoke-RestMethod -Method Post -Uri $Url -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 10)
}

function Assert-Ok {
  param([object]$Response, [string]$Name)
  if ($null -eq $Response -or $Response.errno -ne 0) {
    $message = if ($Response) { $Response.errmsg } else { "empty response" }
    throw "$Name failed: errno=$($Response.errno), errmsg=$message"
  }
}

function Invoke-MysqlScalar {
  param([string]$Sql)
  $previous = $env:MYSQL_PWD
  try {
    $env:MYSQL_PWD = $MysqlPassword
    $result = mysql "-u$MysqlUser" "-N" "-D" $MysqlDatabase "-e" $Sql
    if ($LASTEXITCODE -ne 0) {
      throw "mysql failed: $Sql"
    }
  } finally {
    $env:MYSQL_PWD = $previous
  }
  return (($result | Select-Object -Last 1) -as [string]).Trim()
}

Write-Host "Checking service pages..."
if ((Invoke-WebRequest -UseBasicParsing -Uri $UserFrontendUrl -TimeoutSec 20).StatusCode -ne 200) { throw "user frontend unavailable" }
if ((Invoke-WebRequest -UseBasicParsing -Uri $AdminFrontendUrl -TimeoutSec 20).StatusCode -ne 200) { throw "admin frontend unavailable" }
$health = Invoke-RestMethod -Method Get -Uri "$AiServiceBaseUrl/api/v1/health"
if ($health.status -ne "ok") { throw "AI service health failed" }

Write-Host "Seeding demo products..."
powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "seed-demo-products.ps1") -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase | Write-Host

Write-Host "Customer login..."
$login = Invoke-JsonPost -Url "$WxBaseUrl/wx/auth/login" -Headers @{} -Body @{ username = $CustomerUsername; password = $CustomerPassword }
Assert-Ok $login "customer login"
$wxHeaders = @{ "X-Litemall-Token" = $login.data.token }

Write-Host "Browse goods and submit order..."
$detail = Invoke-RestMethod -Method Get -Uri "$WxBaseUrl/wx/goods/detail?id=$GoodsId" -Headers $wxHeaders
Assert-Ok $detail "goods detail"
$productId = $detail.data.productList[0].id
$cart = Invoke-JsonPost -Url "$WxBaseUrl/wx/cart/fastadd" -Headers $wxHeaders -Body @{ goodsId = $GoodsId; productId = $productId; number = 1 }
Assert-Ok $cart "cart fastadd"
$cartId = [int]$cart.data
$checkout = Invoke-RestMethod -Method Get -Uri "$WxBaseUrl/wx/cart/checkout?cartId=$cartId&couponId=-1&userCouponId=-1&grouponRulesId=0" -Headers $wxHeaders
Assert-Ok $checkout "cart checkout"
$addressId = [int]$checkout.data.addressId
if ($addressId -le 0) { throw "customer default address missing" }
$submit = Invoke-JsonPost -Url "$WxBaseUrl/wx/order/submit" -Headers $wxHeaders -Body @{
  cartId = $cartId
  addressId = $addressId
  couponId = -1
  userCouponId = -1
  grouponRulesId = 0
  grouponLinkId = 0
  message = "E-Review Agent v1.0.1 full flow check"
}
Assert-Ok $submit "order submit"
$orderId = [int]$submit.data.orderId

Write-Host "Demo payment, shipping, receipt..."
Assert-Ok (Invoke-JsonPost -Url "$WxBaseUrl/wx/ai-demo/order/mock-pay" -Headers $wxHeaders -Body @{ orderId = $orderId }) "demo payment"
Assert-Ok (Invoke-JsonPost -Url "$WxBaseUrl/wx/ai-demo/order/mock-ship" -Headers $wxHeaders -Body @{ orderId = $orderId }) "demo shipping"
Assert-Ok (Invoke-JsonPost -Url "$WxBaseUrl/wx/order/confirm" -Headers $wxHeaders -Body @{ orderId = $orderId }) "confirm receipt"

$orderDetail = Invoke-RestMethod -Method Get -Uri "$WxBaseUrl/wx/order/detail?orderId=$orderId" -Headers $wxHeaders
Assert-Ok $orderDetail "order detail"
$orderGoodsId = [int]$orderDetail.data.orderGoods[0].id

Write-Host "Submit real litemall_comment review..."
$reviewText = "收到后包装破损，商品很差，已经申请售后退款，E-Review Agent 自动巡检测试 " + (Get-Date -Format "yyyyMMddHHmmss")
Assert-Ok (Invoke-RestMethod -Method Get -Uri "$WxBaseUrl/wx/order/goods?ogid=$orderGoodsId" -Headers $wxHeaders) "order goods"
Assert-Ok (Invoke-JsonPost -Url "$WxBaseUrl/wx/order/comment" -Headers $wxHeaders -Body @{
  orderGoodsId = $orderGoodsId
  content = $reviewText
  star = 1
  hasPicture = $true
  picUrls = @("http://localhost:6255/static/demo-review-risk.png")
}) "order comment"

$commentId = [int](Invoke-MysqlScalar "select comment from litemall_order_goods where id=$orderGoodsId and deleted=0 limit 1;")
if ($commentId -le 0) { throw "litemall_comment record not found" }

Write-Host "Admin login and Agent patrol..."
$adminLogin = Invoke-JsonPost -Url "$AdminBaseUrl/admin/auth/login" -Headers @{} -Body @{ username = $AdminUsername; password = $AdminPassword }
Assert-Ok $adminLogin "admin login"
$adminHeaders = @{ "X-Litemall-Admin-Token" = $adminLogin.data.token }
Assert-Ok (Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/dashboard/summary" -Headers $adminHeaders) "dashboard summary"
$commentList = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/comment/list?page=1&limit=10&valueId=$GoodsId" -Headers $adminHeaders
Assert-Ok $commentList "admin comment list"
Assert-Ok (Invoke-RestMethod -Method Post -Uri "$AdminBaseUrl/admin/ai/patrol/run-once" -Headers $adminHeaders) "patrol run once"

$analysisId = [int](Invoke-MysqlScalar "select id from litemall_review_ai_analysis where deleted=0 and source_type='litemall_comment' and source_id=$commentId order by id desc limit 1;")
if ($analysisId -le 0) { throw "analysis for litemall_comment $commentId not found" }

$riskList = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/risk/list?page=1&limit=20" -Headers $adminHeaders
Assert-Ok $riskList "risk list"
$riskTaskIdText = Invoke-MysqlScalar "select id from litemall_ai_review_risk_task where deleted=0 and analysis_id=$analysisId order by id desc limit 1;"
if (-not $riskTaskIdText) { throw "risk task for analysis $analysisId not found" }
$riskTaskId = [int]$riskTaskIdText

Write-Host "Handle operation and check Agent pages..."
Assert-Ok (Invoke-JsonPost -Url "$AdminBaseUrl/admin/ai/operation/handle" -Headers $adminHeaders -Body @{
  riskTaskId = $riskTaskId
  actionType = "accept_ai_suggestion"
  newStatus = "processed"
  operator = "admin"
  note = "Full UI flow check handled this risk task."
  feedbackType = "accept"
  feedbackNote = "Accepted in v1.0.1 full flow check."
}) "operation handle"
Assert-Ok (Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/agent/run/list?page=1&limit=10" -Headers $adminHeaders) "agent run list"
Assert-Ok (Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/agent/eval/summary" -Headers $adminHeaders) "agent eval summary"
$framework = Invoke-RestMethod -Method Get -Uri "$AdminBaseUrl/admin/ai/agent/framework/status" -Headers $adminHeaders
Assert-Ok $framework "agent framework status"
if (($framework | ConvertTo-Json -Depth 8) -match "Unexpected UTF-8 BOM") { throw "framework status still contains UTF-8 BOM error" }

[ordered]@{
  customer = "PASS"
  admin = "PASS"
  orderId = $orderId
  commentId = $commentId
  analysisId = $analysisId
  riskTaskId = $riskTaskId
  productId = $GoodsId
  result = "FULL_UI_FLOW_PASS"
  endToEnd = "CUSTOMER_ADMIN_END_TO_END_PASS"
} | ConvertTo-Json -Depth 8
