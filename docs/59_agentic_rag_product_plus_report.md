# Agentic RAG Product Plus Report

## Scope

v1.0.4-agentic-rag-product-plus strengthens the already stable customer-to-admin review loop with product-level Agentic RAG capabilities. This stage does not add real payment, real logistics, real refunds, Qdrant, LangGraph production orchestration, or external model keys.

## Implemented Enhancements

| Area | Result |
| --- | --- |
| Agent state snapshot | `litemall_ai_agent_run.state_snapshot_json` stores compact run state for replay and inspection. |
| Agent role metadata | `litemall_ai_agent_step.agent_role` and `agent_goal` classify each step into lightweight roles. |
| Replay comparison | Run replay creates a new run and compares sentiment, confidence, fallback, and similar cases. |
| Trace UI | Agent Trace now shows run state snapshot, role summaries, replay history, and compare output. |
| Multi-role display | Review Analyst Agent, Risk Auditor Agent, Operation Advisor Agent, and Case Retriever Agent are visible in traces. |
| Case RAG productization | Case retrieval returns IDs, source, match score, retrieval reason, evidence snippet, feedback type, and operation result. |
| Quality evaluation | 30 golden samples generate `docs/58_agent_rag_quality_eval_report.md`. |
| Diagnostics | Agent Eval shows service health and failure groups with repair suggestions. |
| Human feedback | Eval continues to show feedback distribution and acceptance signals. |

## New Or Enhanced APIs

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/admin/ai/agent/run/state/{runId}` | Return run detail, state snapshot, role step summary, and source analysis. |
| GET | `/admin/ai/agent/run/compare` | Compare two runs by key Agent outputs. |
| GET | `/admin/ai/agent/diagnostics/failure-groups` | Return grouped failure types and fix suggestions. |
| GET | `/admin/ai/agent/diagnostics/health` | Check local AI/admin/wx/H5/admin frontend/MySQL health. |
| POST | `/admin/ai/case/rebuild-from-history` | Alias for rebuilding local case memory from historical handling data. |

## Database Migration

`litemall-db/sql/litemall_ai_agent_v104_state.sql` adds:

- `litemall_ai_agent_run.state_snapshot_json`
- `litemall_ai_agent_step.agent_role`
- `litemall_ai_agent_step.agent_goal`

The migration is written to be re-runnable on the local MySQL schema.

## Known Non-Goals

- No real online payment.
- No real logistics provider.
- No real refund workflow.
- No vector database claim.
- No distributed Agent scheduler lock.
- No production SaaS SLA claim.

## Acceptance Evidence

- `python -m pytest` passed.
- `mvn -DskipTests package` passed.
- `scripts/e-review-agent-quality-check.ps1` outputs `AGENT_QUALITY_CHECK_PASS`.
- Remaining full frontend builds and acceptance scripts must be run before tagging.

## v1.1 Experimental Extension

The product-plus baseline is extended by `v1.1-agent-platform-enterprise-gap`. The extension adds enterprise-facing Agent platform surfaces while preserving the v1.0.4 main loop. It should be presented as an enhancement and not as a replacement for the stable defense package.
