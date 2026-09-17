# Frontend Design Notes

## Admin Frontend

The admin frontend is based on Vue 2 and the existing litemall admin application. The AI Workbench is integrated as a business module rather than a standalone landing page.

Main AI pages:

- AI Dashboard
- AI Review Analysis
- Product Comment AI Analysis
- Demo Review Submission
- Agent Patrol Center
- Risk Review Center
- Operation Handling Center
- Agent Run Trace
- Agent Eval
- Agent Configuration Center
- AI Case Knowledge Base

## Design Goals

- Keep the original litemall admin modules usable.
- Make AI governance pages look like a coherent product area.
- Use concise titles, subtitles, metric cards, tables, drawers, timelines, and clear empty states.
- Display risk level, sentiment, confidence, fallback status, and human feedback in a way suitable for screenshots and defense explanation.

## v1.0.4 Product UI Additions

- Agent Trace shows Agent state snapshots, role summaries, replay history, and run comparison without leaving the page.
- Agent Eval shows health cards, grouped failures, quality metrics, RAG retrieval stats, and human feedback distribution.
- The pages avoid `undefined`, `null`, and raw stack traces in visible product copy.
- The UI presents Qdrant and external model integrations as future extensions, not as completed runtime dependencies.
- Avoid exposing local paths, raw stack traces, API keys, or external links in user-facing UI.

## H5 Customer Frontend

The H5 customer side uses `litemall-vue` and supports the defense loop:

1. Browse demo products.
2. Enter product detail.
3. Submit an order.
4. Use demo payment.
5. Use demo shipping.
6. Confirm receipt.
7. Submit a real product review.
8. Let the admin-side Agent patrol analyze the review.

The H5 UI keeps the original litemall style and adds only the minimum demo wording needed for the graduation scenario.

## UI Consistency Rules

- AI recommendations must include a "for operation assistance only" reminder.
- Empty states should explain what the operator can do next.
- Buttons should use professional demo wording, such as "Demo payment success" and "Demo shipping".
- Frontend text should not show `undefined`, `null`, or `NaN`.
- Product pages and admin pages should remain separated but connected through the customer-review-to-Agent closed loop.
