# v1.0.2 H5 Customer UI Manual Regression Report

## Main Path

1. Open `http://localhost:6255`.
2. Login with `user123 / user123`.
3. Open demo product `1181000`.
4. Buy now or add to cart.
5. Submit order.
6. Click demo payment.
7. Click demo shipping.
8. Confirm receipt.
9. Submit a text/image review.
10. Confirm the review is visible in admin comment list.

## Stable Demo Products

| Goods ID | Purpose | Seed Result |
| --- | --- | --- |
| `1181000` | Main path | Purchasable after seed |
| `1006007` | Backup | Purchasable after seed |
| `1006013` | Backup | Purchasable after seed |

## Evidence

- `scripts\seed-demo-products.ps1`: resets stock and sale status, expected marker `DEMO_PRODUCT_SEED_PASS`
- `scripts\e-review-customer-loop-check.ps1`: customer loop regression
- `scripts\e-review-full-ui-flow-check.ps1`: customer to admin end-to-end regression

## Manual Acceptance

| Item | Expected |
| --- | --- |
| H5 home | Opens without blank screen |
| Login | `user123 / user123` works |
| Goods detail | Demo product visible |
| Purchase | No stock blocking on demo product |
| Demo payment/shipping | Buttons complete status progression |
| Receipt | Order enters commentable state |
| Review | Comment is inserted into `litemall_comment` |
| Admin visibility | Admin comment list can see the review |

## Notes

The system still does not use real payment, real logistics, or real refund. This is intentional for graduation demonstration.
