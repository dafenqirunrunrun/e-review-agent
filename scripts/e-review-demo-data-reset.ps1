param(
  [string]$Root = "",
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$MysqlDatabase = "litemall",
  [switch]$CleanGeneratedDemoRecords,
  [switch]$CreateStandardReview
)

$ErrorActionPreference = "Stop"

. (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "e-review-db-common.ps1")
$db = Get-EReviewDbConfig -Root $Root -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase

$seedScript = Join-Path $db.Root "scripts\seed-demo-products.ps1"
if (Test-Path $seedScript) {
  powershell -ExecutionPolicy Bypass -File $seedScript -MysqlUser $db.User -MysqlPassword $db.Password -MysqlDatabase $db.Database | Out-Host
} else {
  Invoke-EReviewMysql -Db $db -Sql "update litemall_goods set is_on_sale=1, deleted=0, update_time=now() where id in (1181000,1006007,1006013); update litemall_goods_product set number=300, deleted=0, update_time=now() where goods_id in (1181000,1006007,1006013);" | Out-Null
}

if ($CleanGeneratedDemoRecords) {
  Invoke-EReviewMysql -Db $db -Sql @"
delete from litemall_ai_operation_log where task_id in (select id from litemall_ai_review_risk_task where source_type in ('demo_review','litemall_comment') and add_time >= date_sub(now(), interval 30 day));
delete from litemall_ai_review_risk_task where source_type in ('demo_review','litemall_comment') and add_time >= date_sub(now(), interval 30 day);
delete from litemall_review_ai_analysis where source_type in ('demo_review','litemall_comment') and add_time >= date_sub(now(), interval 30 day);
"@ | Out-Null
}

if ($CreateStandardReview) {
  Invoke-EReviewMysql -Db $db -Sql @"
insert into litemall_comment(value_id, type, content, user_id, has_picture, pic_urls, star, add_time, update_time, deleted)
select 1181000, 0, '答辩演示标准评价：商品包装破损，图片与描述不一致，希望尽快售后处理。', 1, 0, '[]', 2, now(), now(), 0
where not exists (
  select 1 from litemall_comment
  where value_id=1181000 and content='答辩演示标准评价：商品包装破损，图片与描述不一致，希望尽快售后处理。' and deleted=0
);
"@ | Out-Null
}

powershell -ExecutionPolicy Bypass -File (Join-Path $db.Root "scripts\e-review-db-check.ps1") -MysqlUser $db.User -MysqlPassword $db.Password -MysqlDatabase $db.Database | Out-Host

Write-Host "DEMO_DATA_RESET_PASS"
