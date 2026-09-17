# V2.5 Agentic Policy RAG

This phase adds a lightweight, opt-in Planner/Execution/Reflection workflow for review governance and a structure-aware public policy RAG layer.

## Runtime Switch

- `E_REVIEW_AGENTIC_WORKFLOW_ENABLED=false` keeps the legacy `/api/v1/review/analyze` behavior.
- Set `E_REVIEW_AGENTIC_WORKFLOW_ENABLED=true` to route review analysis through `IntentRouterAgent`, strict policy evidence retrieval when needed, and `ReflectionAgent`.
- `E_REVIEW_AGENTIC_MAX_ITERATIONS=2` bounds replan loops.
- `E_REVIEW_AGENTIC_INTENT_ROUTER_PROVIDER=local_qwen` enables an optional local Qwen/Qwen2.5 intent router; unavailable models fall back to deterministic rules.

## Policy RAG

- Complex documents can be parsed through optional external MinerU by setting `MINERU_CLI`.
- If MinerU is unavailable, parser fallback keeps local demos and tests running.
- Policy chunks are structure-aware: heading, section path, clause id, parent chunk id, source URL, license class, risk types, evidence tags, and content hash are preserved.
- Retrieval uses BM25-style lexical scoring plus metadata boosts for risk hints. This is the safe fallback path; dense BGE-M3/FAISS can be layered on later using existing Agent-RAG hooks.

## Evidence Sources

Seeded public reference sources include FTC/eCFR Part 465, Google Maps UGC policy, Amazon Customer Reviews guidelines, China E-Commerce Law, and Online Transaction Supervision rules.

Platform policy sources are treated as public reference material, not open redistribution material. Runtime evidence should expose bounded snippets, source names, source URLs, section paths, and hashes.
