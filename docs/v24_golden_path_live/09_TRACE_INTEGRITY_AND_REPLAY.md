# Trace Integrity And Replay

Trace integrity and replay evidence: PASS_WITH_WARNINGS.

## Main Run

- Run ID: `4`.
- Request ID: `goldenpath-live-faiss-20260728145605`.
- Evidence ID: `06109824d6541a3ef51df684`.
- Audit integrity: `VALID`.
- Agent path nodes: request validation, security governance, intent classification, retrieval, rerank, grounded local LLM analysis, rule validation, evidence persistence.

## Replay

- First replay run `5`: reached retrieval but fell back because Qwen output JSON was invalid under `AGENT_LLM_MAX_OUTPUT_TOKENS=128`.
- Minimal config fix: raised Golden Path verification output token budget to `256`.
- Second replay run `6`: `grounded-local-llm-rag`, `fallbackUsed=false`, audit integrity `VALID`.
- Compare evidence: `runtime-evidence/http/admin_agent_rag_compare_run4_run6.json`.

## Side Effects

After replay, duplicate, and five concurrency requests:

- `litemall_comment` row count remained focused on the single new Golden Path comment.
- `litemall_review_ai_analysis` remained `1` for the real H5 comment.
- `litemall_ai_review_risk_task` remained `2` for the real H5 comment.
- Duplicate run-4 request returned `idempotentReplay=true` and did not create a second run with the same idempotency key.

Evidence: `runtime-evidence/database/side_effect_guard_after_replay_duplicate_concurrency.txt`.
