# Failures And Fixes

## Recorded Failures

1. `litemall_schema.sql` was not used because it targets the original `litemall` database. The isolated database was initialized from table/data SQL and AI extension SQL instead.
2. Two AI SQL files had MySQL 8 incompatible/damaged Chinese COMMENT text. ASCII-compatible import copies were generated under this evidence directory only.
3. FastAPI hybrid-real initially failed with `FAISS_INDEX_NOT_CONFIGURED`.
4. The first live FAISS build used the legacy CLS provider, which did not match the runtime FlagEmbedding provider.
5. The first Agent-RAG analyze retry hit Java idempotency and returned an old failed run; a fresh subject/query was used for the live run.
6. Override action `manual-review` was rejected by the admin override enum; the actual override API expects `manual_review`.
7. Replay with output token budget `128` produced `AGENT_RAG_LLM_OUTPUT_JSON_INVALID`; the Golden Path runtime config was raised to `256`.
8. Browser automation failed because the local node_repl kernel started under an ESM package context where `require` was unavailable.

## Minimal Fixes Applied

- Built a live FAISS index in `runtime-evidence/model/live-faiss-index`.
- Added `RAG_INDEX_ROOT` to the Golden Path FastAPI startup config.
- Rebuilt the live index with `RAG_BGE_M3_PROVIDER_IMPL=flagembedding`.
- Increased `AGENT_LLM_MAX_OUTPUT_TOKENS` from `128` to `256` in the Golden Path startup config.

No business logic, database schema, production configuration, push, tag, or release was performed.
