# Architecture

E-Review Agent connects a customer H5 storefront, an admin console, Spring Boot APIs, MySQL persistence and a FastAPI AI service.

## Runtime Components

- Customer H5: product browsing, order demo flow and review submission.
- Admin Console: AI dashboard, review analysis, patrol center, risk center and operation center.
- Spring Boot Backend: wx-api, admin-api, database access, patrol scheduling and workflow APIs.
- FastAPI AI Service: review analysis, schema validation, optional provider adapters and experimental retrieval.
- MySQL: commerce data, review analysis results, risk tasks, patrol logs and operation logs.

## Review Governance Flow

1. A customer publishes a text/image review after the demo order flow.
2. The backend writes the review into the original litemall comment table.
3. The inspection Agent scans unprocessed comments.
4. The AI service returns structured analysis.
5. The backend persists analysis and creates risk tasks when needed.
6. Operators process tasks in the admin console.
7. Dashboard metrics update from persisted records.

## Boundary

Payment, logistics and refund integrations are demo implementations. Local model, VLM and RAG modules are experimental and not required for the core business loop.
