# v1.0.1 Demo Stability Hotfix Report

## Scope

This hotfix stabilizes the manual defense demo path after `v1.0-final-delivery` and `v1.0-defense-assets`.
It does not move existing tags, add real payment, add real logistics, add refunds, or change the system architecture.

## Blocking Issues Found

1. Agent Eval / AI Agent Config could surface `Unexpected UTF-8 BOM`.
2. Some admin pages could return `errno=402` when query params contained `undefined`, `null`, or empty strings.
3. Customer-side purchase demos could be blocked by unstable product stock.
4. AI review analysis could fail because the mock case JSON and analyzer text resources were not clean UTF-8 content.
5. Final acceptance did not yet include a full customer-to-admin flow or document link hygiene check.

## Root Causes And Fixes

| Issue | Root cause | Fix |
| --- | --- | --- |
| UTF-8 BOM | Several Java, XML, Python, JSON, and Markdown files contained BOM bytes. | Removed BOM across source/docs and kept Python JSON loading compatible with `utf-8-sig`. |
| Parameter error | UI query objects could contain undefined-like values; comment service still parsed `undefined` as an integer. | Added admin request param binder, frontend GET param cleanup, and comment query normalization. |
| Stock blocker | Demo depended on arbitrary goods stock. | Added `scripts/seed-demo-products.ps1` and integrated it into customer checks. |
| AI analysis error | Mock analyzer/case data contained corrupted Chinese text. | Rewrote analyzer keywords and case JSON with ASCII Unicode escapes. |
| Weak acceptance | Final acceptance did not prove the full customer/admin path. | Added admin API matrix, full UI flow, manual checklist, and doc link check scripts. |

## Files Changed

Key files:

- `ai-service/app/services/mock_analyzer.py`
- `ai-service/data/review_cases.json`
- `ai-service/app/services/mock_analyzer.py`
- `litemall-admin/src/utils/request.js`
- `litemall-admin-api/src/main/java/org/linlinjava/litemall/admin/web/AdminRequestParamBinder.java`
- `litemall-admin-api/src/main/java/org/linlinjava/litemall/admin/web/AdminAiAgentController.java`
- `litemall-admin-api/src/main/java/org/linlinjava/litemall/admin/web/AdminAiReviewController.java`
- `litemall-db/src/main/java/org/linlinjava/litemall/db/service/LitemallCommentService.java`
- `scripts/seed-demo-products.ps1`
- `scripts/e-review-admin-api-matrix-check.ps1`
- `scripts/e-review-full-ui-flow-check.ps1`
- `scripts/e-review-doc-link-check.ps1`
- `scripts/e-review-ui-manual-checklist.ps1`
- `scripts/e-review-final-acceptance.ps1`

## Demo Products

Recommended fixed demo products:

| Goods ID | Purpose | Seed result |
| --- | --- | --- |
| 1181000 | Primary customer purchase/review demo | on sale, stock reset |
| 1006007 | Backup customer purchase demo | on sale, stock reset |
| 1006013 | Backup customer purchase demo | on sale, stock reset |

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\seed-demo-products.ps1
```

## Regression Evidence

Recorded passing checks during this hotfix:

- `python -m pytest`: 8 passed.
- `mvn -pl litemall-admin-api -am -DskipTests package`: BUILD SUCCESS.
- `scripts/check-services.ps1`: PASS.
- `scripts/e-review-admin-api-matrix-check.ps1`: `ADMIN_API_MATRIX_PASS`.
- `scripts/e-review-full-ui-flow-check.ps1`: `FULL_UI_FLOW_PASS`, `CUSTOMER_ADMIN_END_TO_END_PASS`.
- `scripts/e-review-doc-link-check.ps1`: `DOC_LINK_CHECK_PASS`.
- BOM scan: `BOM_REMAINING=0`.

Full final regression still needs to be run before tagging:

```powershell
python -m pytest
mvn -DskipTests package
cd litemall-admin; npm run build:prod
cd ..\litemall-vue; npm run build:prod
cd ..
powershell -ExecutionPolicy Bypass -File .\scripts\e-review-final-acceptance.ps1
```

## Manual UI Regression Checklist

Use `scripts/e-review-ui-manual-checklist.ps1`, then manually click:

1. Customer H5: login, demo product, submit order, demo payment, demo shipping, confirm receipt, submit review.
2. Admin: Dashboard, product comments, AI review analysis, Agent patrol, risk center, operation center, Run Trace, Agent Eval, AI Agent Config.
3. Confirm no parameter error, internal error, UTF-8 BOM, undefined/null/NaN, stock blocker, or white screen.

## Recommendation

If full regression and manual UI checks pass, tag the release as:

```powershell
git tag v1.0.1-demo-stable
```


## v1.0.2 Admin Mall and H5 Stability

The `v1.0.2-admin-mall-h5-stability` stage adds full admin menu API regression, base litemall data checks, H5 demo product stock seeding, expanded document/source link checks, and manual UI regression checklists. See `docs/49_admin_full_menu_stability_matrix.md`, `docs/50_litemall_base_module_data_check.md`, `docs/51_admin_full_ui_manual_regression_report.md`, `docs/52_h5_customer_ui_manual_regression_report.md`, and `docs/53_v102_admin_mall_h5_stability_report.md`.