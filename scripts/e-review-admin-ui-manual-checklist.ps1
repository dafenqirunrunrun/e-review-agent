param(
  [string]$AdminFrontendUrl = "http://localhost:9527",
  [string]$UserFrontendUrl = "http://localhost:6255"
)

$ErrorActionPreference = "Stop"

$checks = @(
  "Admin login page: $AdminFrontendUrl/#/login",
  "Admin dashboard: $AdminFrontendUrl/#/dashboard",
  "Mall region: $AdminFrontendUrl/#/mall/region",
  "Mall brand: $AdminFrontendUrl/#/mall/brand",
  "Mall category: $AdminFrontendUrl/#/mall/category",
  "Mall order: $AdminFrontendUrl/#/mall/order",
  "Mall aftersale: $AdminFrontendUrl/#/mall/aftersale",
  "Mall issue: $AdminFrontendUrl/#/mall/issue",
  "Mall keyword: $AdminFrontendUrl/#/mall/keyword",
  "Goods list: $AdminFrontendUrl/#/goods/list",
  "Goods create: $AdminFrontendUrl/#/goods/create",
  "Goods comment: $AdminFrontendUrl/#/goods/comment",
  "Promotion ad: $AdminFrontendUrl/#/promotion/ad",
  "Promotion coupon: $AdminFrontendUrl/#/promotion/coupon",
  "Promotion topic: $AdminFrontendUrl/#/promotion/topic",
  "Promotion groupon rule: $AdminFrontendUrl/#/promotion/groupon-rule",
  "System admin: $AdminFrontendUrl/#/sys/admin",
  "System notice: $AdminFrontendUrl/#/sys/notice",
  "System log: $AdminFrontendUrl/#/sys/log",
  "System role: $AdminFrontendUrl/#/sys/role",
  "Storage: $AdminFrontendUrl/#/sys/os",
  "Config mall: $AdminFrontendUrl/#/config/mall",
  "Config express: $AdminFrontendUrl/#/config/express",
  "Config order: $AdminFrontendUrl/#/config/order",
  "Config wx: $AdminFrontendUrl/#/config/wx",
  "AI dashboard: $AdminFrontendUrl/#/ai-workbench/dashboard",
  "AI review: $AdminFrontendUrl/#/ai-workbench/review",
  "AI patrol: $AdminFrontendUrl/#/ai-workbench/patrol",
  "AI risk: $AdminFrontendUrl/#/ai-workbench/risk",
  "AI operation: $AdminFrontendUrl/#/ai-workbench/operation",
  "AI run trace: $AdminFrontendUrl/#/ai-workbench/agent-trace",
  "AI eval: $AdminFrontendUrl/#/ai-workbench/agent-eval",
  "AI config: $AdminFrontendUrl/#/ai-workbench/config",
  "H5 home: $UserFrontendUrl/#/home",
  "H5 demo goods detail: $UserFrontendUrl/#/items/detail/1181000"
)

[ordered]@{
  result = "ADMIN_UI_MANUAL_CHECKLIST_READY"
  rule = "Open each page, confirm no internal error, bad argument, stock blocking, blank screen, undefined/null/NaN, or unexpected external link."
  checklist = $checks
} | ConvertTo-Json -Depth 4
