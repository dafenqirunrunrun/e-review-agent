# V2 Reranker Evaluation

## Fixture Evaluation

The fixture tests validate:

- stable deterministic ordering
- bounded top-k output
- tenant-scope rejection
- inactive candidate rejection
- missing model asset handling
- explicit `real_required` behavior
- invalid model-score fallback
- EvidenceBundle reranker fields

## Gate Script

Run:

```powershell
D:\anaconda\envs\torchtest-phase3a3-tf4\python.exe ai-service/scripts/readiness/run_agent_rag_phase3b_gate.py
```

Expected without a local model:

```text
AGENT_RAG_RERANKER_CONTRACT_PASS
AGENT_RAG_RERANKER_FALLBACK_PASS
AGENT_RAG_MODEL_RERANKER_BLOCKED
AGENT_RAG_PHASE3B_BLOCKED
```

Expected with a verified local model:

```text
AGENT_RAG_MODEL_RERANKER_PASS
AGENT_RAG_PHASE3B_PASS
```

## Interpretation

`AGENT_RAG_PHASE3B_BLOCKED` is not a fixture failure. It means the governed
abstraction and fallback passed, but a real local reranker model was not
available for verification.
