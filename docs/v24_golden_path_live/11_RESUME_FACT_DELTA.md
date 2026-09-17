# Resume Fact Delta

## Newly Resume-Safe Facts

- Built and verified an isolated Golden Path environment using `litemall_v24_verify`, protecting the original `litemall` database.
- Completed a real H5 customer comment flow into `litemall_comment`, then generated AI analysis and risk tasks from that comment.
- Verified a governed Agent-RAG path from Java admin-api to FastAPI with real BGE-M3 retrieval, FAISS recall, FlagEmbedding reranking, and Qwen3-1.7B structured decision, with fallback disabled in the successful main run.
- Persisted citation/evidence bundle, audit hash, human override, and replay comparison records for the same live case.
- Found and fixed a practical replay robustness issue by increasing structured-output token budget from `128` to `256`.
- Ran a five-request concurrent Agent-RAG smoke where all runs completed with `fallbackUsed=false` and `auditIntegrityStatus=VALID`.

## Runtime-Verified But Quality Not Evaluated

- Real model runtime participation is verified, but retrieval/decision quality still needs the planned held-out benchmark.
- The live index contains the small validation corpus only; it is not a production-scale or million-vector index.
- UI HTTP smoke passed, but full browser-driven UI interaction was blocked by local browser runtime setup.

## Still Not Claimable

- Production deployment
- Real payment
- Real logistics
- Real user traffic
- High availability
- Million-scale index
- Multi-Agent
- ReAct
- Unverified metric improvements
