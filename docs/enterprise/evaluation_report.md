# v1.7.0 Enterprise Evaluation Report

Dataset: 160 programmatic project-owned cases under `<data-private>/enterprise-eval-v170/`.

Git-tracked aggregate result: `data/private_research/audit/v170_enterprise_quality_gates.json`.

Current gate status: `V170_ENTERPRISE_RAG_AGENT_ENGINEERING_GATE_PASS`.

Key metrics:

- RAG Hit@1/3/5: 1.0 / 1.0 / 1.0
- MRR: 1.0
- nDCG@5: 1.0
- Citation validity: 1.0
- Agent tool schema valid rate: 1.0
- Human review recall: 1.0
- Prompt injection escapes: 0
- Prohibited tool calls: 0
- Idempotency consistency: 1.0
- Adapter schema valid: 1.0
- Adapter fallback: 0.0
- Failure injection: PASS

These metrics validate local engineering behavior on programmatic test cases only.
