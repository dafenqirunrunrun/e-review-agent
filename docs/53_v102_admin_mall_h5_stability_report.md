# v1.0.2 Admin Mall and H5 Stability Report

## Goal

v1.0.2 focuses on non-AI admin modules and H5 purchase/review stability while preserving the AI workbench delivered in v1.0.1.

## Fix Summary

| Problem | Root Cause | Fix |
| --- | --- | --- |
| Non-AI admin list pages returned `参数值不对` | Old controllers relied on Java parameter names, but the build did not retain them reliably | Added Java compiler `-parameters` and tolerant sort/order validators |
| Region/category/stat pages returned internal errors in API checks | Same runtime binding instability surfaced as 402/502 in base modules | Rebuilt admin-api with parameter retention and verified all base APIs |
| H5 purchase could be blocked by stock | Demo data stock could be consumed or unavailable | `seed-demo-products.ps1` resets three stable products |
| Presentation/source external links | Legacy admin/H5 pages included external project/vendor links | Removed external link menu and visible external URLs; expanded doc/source link checker |
| AI workbench regression risk | Non-AI fixes could affect shared admin runtime | AI endpoints included in full menu check and final acceptance |

## Verification Markers

- `DEMO_PRODUCT_SEED_PASS`
- `ADMIN_FULL_MENU_API_PASS`
- `ADMIN_API_MATRIX_PASS`
- `DOC_LINK_CHECK_PASS`
- `FULL_UI_FLOW_PASS`
- `CUSTOMER_ADMIN_END_TO_END_PASS`
- `FINAL_ACCEPTANCE_PASS`

## Current Status

At the time of this report:

- Admin full menu API check: PASS
- Demo product seed: PASS
- Doc/source link check: PASS
- Services check: PASS

Full build and final acceptance must be rerun before creating `v1.0.2-admin-mall-h5-stable`.

## Recommendation

After all automation and manual UI checks pass, tag the release as:

```text
v1.0.2-admin-mall-h5-stable
```

## v1.0.4 Continuity Note

v1.0.4 does not change the core H5 order/review loop or admin mall base modules. The added work focuses on Agent state snapshots, replay comparison, local RAG evidence, diagnostics, and quality-evaluation presentation. Existing v1.0.2 stability gates should remain valid and continue to be part of final acceptance.
