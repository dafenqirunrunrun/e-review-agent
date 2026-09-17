# V2 Local Soak Evaluation

Script:

```powershell
D:\anaconda\envs\torchtest-phase3a3-tf4\python.exe scripts/load/run_agent_rag_local_soak.py --duration-sec 600 --interval-sec 5
```

Output:

- `artifacts/agent-rag/v2.0-observability/local-soak-summary.json`

Pass token:

- `AGENT_RAG_LOCAL_SOAK_PASS`

Evaluation scope:

- Sends steady low-rate analyze requests to the local Python Runtime.
- Confirms request id consistency and records failure count and maximum latency.

Boundary:

- The default 600-second duration is intended for local demo readiness.
- This does not represent production endurance or multi-node reliability.

Latest local result:

```text
AGENT_RAG_LOCAL_SOAK_PASS
durationSec=600
intervalSec=5
```
