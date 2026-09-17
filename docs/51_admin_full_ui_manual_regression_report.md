# v1.0.2 Admin Full UI Manual Regression Report

## Checklist Command

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-admin-ui-manual-checklist.ps1
```

Expected marker: `ADMIN_UI_MANUAL_CHECKLIST_READY`

## Manual Click Scope

| Page | Opens | Loads Data | Popup Error | Blank Screen | Notes |
| --- | --- | --- | --- | --- | --- |
| Login | To be checked manually | N/A | No expected | No expected | Use `admin123 / admin123` |
| Dashboard | API PASS | API PASS | No expected | No expected | `/admin/dashboard` PASS |
| Region | API PASS | API PASS | No expected | No expected | Region list and child list PASS |
| Brand | API PASS | API PASS | No expected | No expected | Brand list PASS |
| Category | API PASS | API PASS | No expected | No expected | Category tree and L1 PASS |
| Order | API PASS | API PASS | No expected | No expected | Order list PASS |
| Aftersale | API PASS | API PASS | No expected | No expected | Aftersale list PASS |
| Goods list/detail/create support data | API PASS | API PASS | No expected | No expected | Goods list/detail/catAndBrand PASS |
| Comment | API PASS | API PASS | No expected | No expected | Comment list PASS |
| Promotion pages | API PASS | API PASS | No expected | No expected | Ad/topic/coupon/groupon PASS |
| User pages | API PASS | API PASS | No expected | No expected | User/address/collect/feedback/footprint/history PASS |
| System pages | API PASS | API PASS | No expected | No expected | Admin/notice/log/role/storage PASS |
| Config pages | API PASS | API PASS | No expected | No expected | Mall/express/order/wx config PASS |
| Stats pages | API PASS | API PASS | No expected | No expected | User/order/goods stats PASS |
| AI workbench | API PASS | API PASS | No expected | No expected | v1.0.1 regression surface preserved |

## Current Evidence

- `scripts\e-review-admin-full-menu-api-check.ps1`: `ADMIN_FULL_MENU_API_PASS`
- `scripts\e-review-doc-link-check.ps1`: `DOC_LINK_CHECK_PASS`
- `scripts\check-services.ps1`: `PASS`

## Manual Rule

During final screenshot or recording, each page must be opened in the browser. If any page shows `系统内部错误`, `参数值不对`, `Unexpected UTF-8 BOM`, `undefined/null/NaN`, or a blank page, the release must stop and the issue must be fixed before tagging.
