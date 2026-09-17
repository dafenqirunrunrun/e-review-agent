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
  @{ module = "profile"; name = "notice count"; path = "/admin/profile/nnotice" },
  @{ module = "profile"; name = "notice list"; path = "/admin/profile/lsnotice?page=1&limit=10" },
  @{ module = "dashboard"; name = "dashboard"; path = "/admin/dashboard" },
  @{ module = "mall"; name = "region tree"; path = "/admin/region/list" },
  @{ module = "mall"; name = "region children"; path = "/admin/region/clist?id=0" },
  @{ module = "mall"; name = "brand list"; path = "/admin/brand/list?page=1&limit=10" },
  @{ module = "mall"; name = "category list"; path = "/admin/category/list" },
  @{ module = "mall"; name = "category level1"; path = "/admin/category/l1" },
  @{ module = "mall"; name = "order list"; path = "/admin/order/list?page=1&limit=10" },
  @{ module = "mall"; name = "aftersale list"; path = "/admin/aftersale/list?page=1&limit=10" },
  @{ module = "mall"; name = "issue list"; path = "/admin/issue/list?page=1&limit=10" },
  @{ module = "mall"; name = "keyword list"; path = "/admin/keyword/list?page=1&limit=10" },
  @{ module = "goods"; name = "goods list"; path = "/admin/goods/list?page=1&limit=10" },
  @{ module = "goods"; name = "goods detail"; path = "/admin/goods/detail?id=1181000" },
  @{ module = "goods"; name = "goods cat and brand"; path = "/admin/goods/catAndBrand" },
  @{ module = "goods"; name = "comment list"; path = "/admin/comment/list?page=1&limit=10" },
  @{ module = "promotion"; name = "ad list"; path = "/admin/ad/list?page=1&limit=10" },
  @{ module = "promotion"; name = "topic list"; path = "/admin/topic/list?page=1&limit=10" },
  @{ module = "promotion"; name = "coupon list"; path = "/admin/coupon/list?page=1&limit=10" },
  @{ module = "promotion"; name = "coupon user list"; path = "/admin/coupon/listuser?page=1&limit=10" },
  @{ module = "promotion"; name = "groupon rule list"; path = "/admin/groupon/list?page=1&limit=10" },
  @{ module = "promotion"; name = "groupon record list"; path = "/admin/groupon/listRecord?page=1&limit=10" },
  @{ module = "user"; name = "user list"; path = "/admin/user/list?page=1&limit=10" },
  @{ module = "user"; name = "address list"; path = "/admin/address/list?page=1&limit=10" },
  @{ module = "user"; name = "collect list"; path = "/admin/collect/list?page=1&limit=10" },
  @{ module = "user"; name = "feedback list"; path = "/admin/feedback/list?page=1&limit=10" },
  @{ module = "user"; name = "footprint list"; path = "/admin/footprint/list?page=1&limit=10" },
  @{ module = "user"; name = "history list"; path = "/admin/history/list?page=1&limit=10" },
  @{ module = "system"; name = "admin list"; path = "/admin/admin/list?page=1&limit=10" },
  @{ module = "system"; name = "notice list"; path = "/admin/notice/list?page=1&limit=10" },
  @{ module = "system"; name = "log list"; path = "/admin/log/list?page=1&limit=10" },
  @{ module = "system"; name = "role list"; path = "/admin/role/list?page=1&limit=10" },
  @{ module = "system"; name = "role options"; path = "/admin/role/options" },
  @{ module = "system"; name = "storage list"; path = "/admin/storage/list?page=1&limit=10" },
  @{ module = "config"; name = "mall config"; path = "/admin/config/mall" },
  @{ module = "config"; name = "express config"; path = "/admin/config/express" },
  @{ module = "config"; name = "order config"; path = "/admin/config/order" },
  @{ module = "config"; name = "wx config"; path = "/admin/config/wx" },
  @{ module = "stat"; name = "user stat"; path = "/admin/stat/user" },
  @{ module = "stat"; name = "order stat"; path = "/admin/stat/order" },
  @{ module = "stat"; name = "goods stat"; path = "/admin/stat/goods" },
  @{ module = "ai"; name = "ai dashboard"; path = "/admin/ai/dashboard/summary" },
  @{ module = "ai"; name = "ai review list"; path = "/admin/ai/review/list?page=1&limit=10" },
  @{ module = "ai"; name = "ai risk list"; path = "/admin/ai/risk/list?page=1&limit=10" },
  @{ module = "ai"; name = "ai operation list"; path = "/admin/ai/operation/list?page=1&limit=10" },
  @{ module = "ai"; name = "ai patrol status"; path = "/admin/ai/patrol/status" },
  @{ module = "ai"; name = "ai patrol logs"; path = "/admin/ai/patrol/logs?page=1&limit=10" },
  @{ module = "ai"; name = "ai agent run list"; path = "/admin/ai/agent/run/list?page=1&limit=10" },
  @{ module = "ai"; name = "ai agent eval summary"; path = "/admin/ai/agent/eval/summary" },
  @{ module = "ai"; name = "ai agent quality summary"; path = "/admin/ai/agent/quality/summary" },
  @{ module = "ai"; name = "ai agent diagnostics summary"; path = "/admin/ai/agent/diagnostics/summary" },
  @{ module = "ai"; name = "ai agent diagnostics failures"; path = "/admin/ai/agent/diagnostics/recent-failures" },
  @{ module = "ai"; name = "ai agent diagnostics groups"; path = "/admin/ai/agent/diagnostics/failure-groups" },
  @{ module = "ai"; name = "ai agent diagnostics health"; path = "/admin/ai/agent/diagnostics/health" },
  @{ module = "ai"; name = "ai agent framework"; path = "/admin/ai/agent/framework/status" },
  @{ module = "ai"; name = "ai case list"; path = "/admin/ai/case/list?page=1&limit=10" },
  @{ module = "ai"; name = "ai case retrieve"; path = "/admin/ai/case/retrieve?query=demo&riskType=after_sales&topK=3" },
  @{ module = "ai"; name = "ai case retrieve v2"; path = "/admin/ai/case/retrieve-v2?query=refund%20package%20damaged&riskType=after_sales_risk&strategy=hybrid&topK=3" },
  @{ module = "ai"; name = "ai case retrieve compare"; path = "/admin/ai/case/retrieve-compare?query=refund%20package%20damaged&riskType=after_sales_risk&topK=3" },
  @{ module = "ai"; name = "ai case retrieval failures"; path = "/admin/ai/case/retrieval/failures" },
  @{ module = "ai"; name = "ai case retrieval metrics"; path = "/admin/ai/case/retrieval/metrics" },
  @{ module = "ai"; name = "ai agentops summary"; path = "/admin/ai/agentops/summary" },
  @{ module = "ai"; name = "ai tool registry"; path = "/admin/ai/tool/registry/list" },
  @{ module = "ai"; name = "ai tool manifest local"; path = "/admin/ai/tool/manifest/local" },
  @{ module = "ai"; name = "ai tool schema validate"; path = "/admin/ai/tool/schema/validate" },
  @{ module = "ai"; name = "ai tool execution summary"; path = "/admin/ai/tool/execution/summary" },
  @{ module = "ai"; name = "ai tool policy"; path = "/admin/ai/tool/policy/list" },
  @{ module = "ai"; name = "ai memory profiles"; path = "/admin/ai/memory/profile/list?page=1&limit=10" },
  @{ module = "ai"; name = "ai guardrail summary"; path = "/admin/ai/guardrail/summary" },
  @{ module = "ai"; name = "ai agent registry"; path = "/admin/ai/agent/registry/list" },
  @{ module = "ai"; name = "ai rag quality"; path = "/admin/ai/rag/quality/summary" }
)

$results = @()
foreach ($check in $checks) {
  $url = "$AdminBaseUrl$($check.path)"
  try {
    $response = Invoke-RestMethod -Method Get -Uri $url -Headers $headers
    Assert-Ok $response $check.path
    $results += [ordered]@{
      module = $check.module
      name = $check.name
      path = $check.path
      status = "PASS"
      errno = $response.errno
    }
  } catch {
    $results += [ordered]@{
      module = $check.module
      name = $check.name
      path = $check.path
      status = "FAIL"
      error = $_.Exception.Message
    }
  }
}

$failed = @($results | Where-Object { $_.status -ne "PASS" })
[ordered]@{
  total = $results.Count
  passed = ($results | Where-Object { $_.status -eq "PASS" }).Count
  failed = $failed.Count
  checks = $results
  result = if ($failed) { "FAIL" } else { "ADMIN_FULL_MENU_API_PASS" }
} | ConvertTo-Json -Depth 8

if ($failed) {
  exit 1
}
