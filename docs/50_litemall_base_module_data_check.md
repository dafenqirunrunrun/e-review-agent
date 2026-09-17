# v1.0.2 Litemall Base Module Data Check

## Database Scope

Database: `litemall`

Checked modules:

- Region: `litemall_region`
- Goods: `litemall_goods`, `litemall_goods_product`, `litemall_category`, `litemall_brand`
- Order and comment: `litemall_order`, `litemall_order_goods`, `litemall_comment`
- Promotion and system lists: ad, topic, coupon, groupon, user, role, storage, log

## Demo Product Seed

Command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\seed-demo-products.ps1
```

Expected marker: `DEMO_PRODUCT_SEED_PASS`

Recommended demo goods:

| Goods ID | Role | Requirement |
| --- | --- | --- |
| `1181000` | Main demo product | On sale, not deleted, SKU stock reset to 300 per SKU |
| `1006007` | Backup product | On sale, not deleted, SKU stock reset to 300 |
| `1006013` | Backup product | On sale, not deleted, SKU stock reset to 300 |

## Data Findings

| Item | Result | Notes |
| --- | --- | --- |
| Region table exists | PASS | `/admin/region/list` and `/admin/region/clist?id=0` return `errno=0` |
| Category tree available | PASS | `/admin/category/list` and `/admin/category/l1` return `errno=0` |
| Goods list available | PASS | `/admin/goods/list?page=1&limit=10` returns `errno=0` |
| Goods detail available | PASS | `/admin/goods/detail?id=1181000` returns `errno=0` |
| Goods SKU stock available | PASS | Seed script verifies purchasable status |
| Comment table available | PASS | `/admin/comment/list?page=1&limit=10` returns `errno=0` |
| Admin full menu data queries | PASS | `ADMIN_FULL_MENU_API_PASS` |

## Conclusion

The base litemall modules have enough stable data for graduation demonstration. The stock seed script is repeatable and should be run before recording or defense.
