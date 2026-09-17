# litemall Secondary Development Notes

## Purpose

This project extends the original litemall system into E-Review Agent, an AI-assisted review governance prototype for graduation defense. The original open-source origin is documented in `NOTICE.md`, `THIRD_PARTY_LICENSES.md`, and `docs/23_open_source_compliance.md`.

## Modified Modules

- `litemall-admin-api`: adds admin-side AI review, patrol, risk, operation, Agent trace, Agent evaluation, diagnostics, and case knowledge APIs.
- `litemall-admin`: adds the AI Workbench pages and productized admin UI for review governance.
- `litemall-wx-api`: keeps the original customer API and adds clearly named demo order transition endpoints.
- `litemall-vue`: provides the H5 customer entry for browsing products, creating demo orders, confirming receipt, and posting real product reviews.
- `litemall-db`: contains generated domain, mapper, service code and AI-related SQL migrations.
- `ai-service`: provides the FastAPI review analysis and Agent-style mock/rule workflow.
- `scripts`: provides startup, smoke, full UI flow, quality, encoding, and final acceptance checks.

## Integration Points

- Customer reviews are written into `litemall_comment`.
- Agent patrol scans demo reviews and real `litemall_comment` records when enabled.
- AI analysis results are stored in `litemall_review_ai_analysis`.
- High-risk results generate tasks in `litemall_ai_review_risk_task`.
- Operation handling writes logs and human feedback.
- Dashboard, Risk Center, Operation Center, Agent Trace, Agent Eval, and Case Knowledge pages consume the same closed-loop data.

## Permission And Routing Notes

The admin AI features are organized under the AI Workbench menu. The core permission shape follows existing litemall admin patterns and keeps the original mall management modules intact.

Representative routes:

- `/ai-workbench/dashboard`
- `/ai-workbench/review`
- `/ai-workbench/patrol`
- `/ai-workbench/risk`
- `/ai-workbench/operation`
- `/ai-workbench/agent-trace`
- `/ai-workbench/agent-eval`
- `/ai-workbench/case-knowledge`
- `/ai-workbench/config`

## Development Boundary

The secondary development does not claim to rebuild a full production commerce platform. The customer loop is a defense-ready demo loop:

- no real payment
- no real logistics
- no real refund
- no mandatory OpenAI key
- no mandatory Qdrant dependency
- AI results are for operation assistance only
