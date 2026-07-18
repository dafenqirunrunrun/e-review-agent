# Demo Guide

## Main Demo Path

1. Start MySQL and import the required schema files from `litemall-db/sql/`.
2. Start the FastAPI AI service on port `8008`.
3. Start wx-api on port `8080`.
4. Start admin-api on port `8083`.
5. Start the customer H5 frontend.
6. Start the admin frontend.
7. In the customer H5 app, browse a product and enter the product detail page.
8. Submit an order, use demo payment and demo shipping, then confirm receipt.
9. Submit a text/image review.
10. In the admin console, open the Agent patrol center and run an inspection.
11. Open the risk center to view generated risk tasks.
12. Open the operation center and process a task.
13. Return to Dashboard to view metric changes.

## Backup Demo Path

If the full customer order flow is unavailable, use the backend demo review submission page to create a synthetic review, then run the same Agent patrol, risk and operation workflow.

## Notes

- Use only demo accounts and demo data.
- Do not use real payment, logistics or refund channels.
- Do not show screenshots containing local paths, credentials, phone numbers or real user information.
