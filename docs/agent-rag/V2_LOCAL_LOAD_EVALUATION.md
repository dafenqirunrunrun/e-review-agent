# V2 Local Load Evaluation

Script:

```powershell
D:\anaconda\envs\torchtest-phase3a3-tf4\python.exe scripts/load/run_agent_rag_local_load.py --requests 50 --concurrency 4
```

Output:

- `artifacts/agent-rag/v2.0-observability/local-load-summary.json`

Pass token:

- `AGENT_RAG_LOCAL_LOAD_PASS`

Evaluation scope:

- Verifies concurrent request handling against the local FastAPI Agent-RAG analyze endpoint.
- Checks request id correlation on each response.
- Records success/failure count and latency p50/p95/max.

Boundary:

- This is a local resilience check, not production capacity testing.

Latest local result:

```text
AGENT_RAG_LOCAL_LOAD_PASS
requests=50
concurrency=4
```
