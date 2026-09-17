# v2.0 Agent-RAG Phase 1 Evaluation

Fixture:

- Path: `ai-service/tests/fixtures/agent_rag/phase1_cases.json`
- Case count: 30
- Data type: project-owned synthetic fixture
- Real customer data: not used

Scripts:

- `python ai-service/scripts/evaluation/run_agent_rag_phase1_eval.py`
- `python ai-service/scripts/e2e/run_agent_rag_phase1_e2e.py`
- `python ai-service/scripts/readiness/run_agent_rag_phase1_gate.py`

Evidence output:

- `artifacts/agent-rag/v2.0-phase1/evaluation-summary.json`
- `artifacts/agent-rag/v2.0-phase1/evaluation-report.md`
- `artifacts/agent-rag/v2.0-phase1/e2e-summary.json`
- `artifacts/agent-rag/v2.0-phase1/phase1-gate-result.json`

Gate requirements:

- Tenant isolation violations = 0
- Schema valid rate = 100%
- Fallback correctness = 100%
- Duplicate task count = 0
- Evaluation completed
- Business E2E completed

The gate records real local fixture metrics. It does not claim private model
quality or production Enterprise RAG readiness.
