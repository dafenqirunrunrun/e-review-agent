# v1.0.2 Admin Full Menu Stability Matrix

## Scope

This matrix covers the non-AI mall/admin modules and the AI workbench regression surface for `v1.0.2-admin-mall-h5-stability`.

## API Matrix Result

Command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-admin-full-menu-api-check.ps1
```

Result: `ADMIN_FULL_MENU_API_PASS`

Total checks: 51
Passed checks: 51
Failed checks: 0

## Matrix

| Module | Page | Route | Main API | Current Status | Error Message | Root Cause | Fix Status | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Dashboard | Home | `/dashboard` | `/admin/dashboard` | Normal | None | None | No change | PASS |
| Mall | Region | `/mall/region` | `/admin/region/list`, `/admin/region/clist?id=0` | Fixed | Previously 502/402 | Java parameter names were not retained; region tree needed null-safe data access | Fixed by compiler parameter retention and validation tolerance | PASS |
| Mall | Brand | `/mall/brand` | `/admin/brand/list` | Fixed | Previously bad argument | Old controller parameter binding depended on Java parameter names | Fixed | PASS |
| Mall | Category | `/mall/category` | `/admin/category/list`, `/admin/category/l1` | Fixed | Previously 502 | Old runtime could not bind/filter consistently | Fixed | PASS |
| Mall | Order | `/mall/order` | `/admin/order/list` | Fixed | Previously bad argument | Missing retained parameter names for pagination/sort | Fixed | PASS |
| Mall | Aftersale | `/mall/aftersale` | `/admin/aftersale/list` | Fixed | Previously bad argument | Missing retained parameter names for pagination/sort | Fixed | PASS |
| Mall | Issue | `/mall/issue` | `/admin/issue/list` | Fixed | Previously bad argument | Missing retained parameter names | Fixed | PASS |
| Mall | Keyword | `/mall/keyword` | `/admin/keyword/list` | Fixed | Previously bad argument | Missing retained parameter names | Fixed | PASS |
| Goods | Goods List | `/goods/list` | `/admin/goods/list` | Fixed | Previously bad argument | Missing retained parameter names | Fixed | PASS |
| Goods | Goods Detail | `/goods/edit?id=...` | `/admin/goods/detail?id=1181000` | Fixed | Previously bad argument | Missing retained parameter names | Fixed | PASS |
| Goods | Cat and Brand | `/goods/create` | `/admin/goods/catAndBrand` | Fixed | Previously 502 | Dependent base queries stabilized after binding fix | Fixed | PASS |
| Goods | Comment | `/goods/comment` | `/admin/comment/list` | Normal | None | v1.0.1 already normalized undefined/null filters | No change | PASS |
| Promotion | Ad | `/promotion/ad` | `/admin/ad/list` | Fixed | Previously bad argument | Missing retained parameter names | Fixed | PASS |
| Promotion | Topic | `/promotion/topic` | `/admin/topic/list` | Fixed | Previously bad argument | Missing retained parameter names | Fixed | PASS |
| Promotion | Coupon | `/promotion/coupon` | `/admin/coupon/list`, `/admin/coupon/listuser` | Fixed | Previously bad argument | Missing retained parameter names | Fixed | PASS |
| Promotion | Groupon | `/promotion/groupon-rule`, `/promotion/groupon-activity` | `/admin/groupon/list`, `/admin/groupon/listRecord` | Fixed | Previously bad argument | Missing retained parameter names | Fixed | PASS |
| User | Member | `/user/user` | `/admin/user/list` | Fixed | Previously bad argument | Missing retained parameter names | Fixed | PASS |
| User | Address/Collect/Feedback/Footprint/Search | `/user/*` | `/admin/address/list`, `/admin/collect/list`, `/admin/feedback/list`, `/admin/footprint/list`, `/admin/history/list` | Fixed | Previously bad argument | Missing retained parameter names | Fixed | PASS |
| System | Admin/Notice/Log/Role/Storage | `/sys/*` | `/admin/admin/list`, `/admin/notice/list`, `/admin/log/list`, `/admin/role/list`, `/admin/storage/list` | Fixed | Previously bad argument | Missing retained parameter names | Fixed | PASS |
| Config | Mall/Express/Order/Wx | `/config/*` | `/admin/config/*` | Normal | None | None | No change | PASS |
| Stats | User/Order/Goods | `/stat/*` | `/admin/stat/*` | Fixed | Previously 502 | Base module query stability improved by rebuilt admin-api and parameter retention | Fixed | PASS |
| AI Workbench | All core AI pages | `/ai-workbench/*` | `/admin/ai/*` | Regression pass | None | v1.0.1 fixes retained | No regression | PASS |

## Conclusion

The full admin menu API surface is stable for demonstration. Manual UI click-through should use `scripts\e-review-admin-ui-manual-checklist.ps1` as the checklist companion.
