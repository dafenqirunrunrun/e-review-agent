param(
  [string]$MysqlUser = "",
  [string]$MysqlPassword = "",
  [string]$MysqlDatabase = "litemall",
  [int[]]$GoodsIds = @(1181000, 1006007, 1006013),
  [int]$Stock = 300
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$common = Join-Path $scriptDir "e-review-db-common.ps1"
if (Test-Path $common) {
  . $common
  $db = Get-EReviewDbConfig -MysqlUser $MysqlUser -MysqlPassword $MysqlPassword -MysqlDatabase $MysqlDatabase
  $MysqlUser = $db.User
  $MysqlPassword = $db.Password
  $MysqlDatabase = $db.Database
} elseif (-not $MysqlPassword) {
  $MysqlPassword = $env:EREVIEW_MYSQL_PASSWORD
}

if (-not $MysqlPassword) {
  throw "MySQL password not provided. Set EREVIEW_MYSQL_PASSWORD or pass -MysqlPassword."
}

if ($GoodsIds.Count -lt 1) {
  throw "GoodsIds must not be empty"
}

$ids = ($GoodsIds | ForEach-Object { [int]$_ }) -join ","
$sql = @"
update litemall_goods
set is_on_sale = 1,
    deleted = 0,
    is_hot = 1,
    update_time = now()
where id in ($ids);

update litemall_goods_product
set number = $Stock,
    deleted = 0,
    update_time = now()
where goods_id in ($ids);

select g.id as goods_id,
       g.name as goods_name,
       g.is_on_sale,
       g.deleted,
       min(p.price) as min_price,
       sum(p.number) as total_stock,
       count(p.id) as sku_count,
       case when g.is_on_sale = 1 and g.deleted = 0 and sum(p.number) > 0 then 'YES' else 'NO' end as purchasable
from litemall_goods g
join litemall_goods_product p on p.goods_id = g.id and p.deleted = 0
where g.id in ($ids)
group by g.id, g.name, g.is_on_sale, g.deleted
order by g.id;
"@

Write-Host "Seeding stable customer demo products..."
Write-Host "Goods IDs: $ids"
$previous = $env:MYSQL_PWD
try {
  $env:MYSQL_PWD = $MysqlPassword
  & mysql "-u$MysqlUser" "-D" $MysqlDatabase "-e" $sql
  if ($LASTEXITCODE -ne 0) {
    throw "mysql demo product seed failed"
  }
} finally {
  $env:MYSQL_PWD = $previous
}

Write-Host "DEMO_PRODUCT_SEED_PASS"
