# Phase 4 Grounded Optional Local LLM

## Goal

Phase 4 adds a governed optional local LLM decision path for Agent-RAG. It does not replace the stable deterministic decision path by default.

## Default Behavior

The default remains deterministic:

```text
AGENT_RAG_LLM_PROVIDER=deterministic
AGENT_RAG_LOCAL_LLM_ENABLED=false
```

In this mode, Agent-RAG behavior is unchanged.

## Optional Local Qwen Path

To request the local model path:

```text
AGENT_RAG_LLM_PROVIDER=local_qwen3_transformers
AGENT_RAG_LOCAL_LLM_ENABLED=true
E_REVIEW_LOCAL_QWEN_MODEL_DIR=<local model directory>
```

The runtime uses the existing local Qwen Transformers provider. Model files must already exist locally. The code does not download model weights.

## Grounding Rule

When `AGENT_RAG_LOCAL_LLM_REQUIRE_GROUNDED_CONTEXT=true`, the local LLM is called only if retrieval returned at least one citation. If no grounded evidence exists, the request falls back to deterministic governed rules with:

```text
AGENT_RAG_LLM_NO_GROUNDED_CONTEXT
```

## Contract Rule

The local LLM must return strict JSON matching:

```json
{
  "riskLevel": "low|medium|high",
  "riskTypes": ["normal_review|negative_review|after_sales_risk|safety_or_fraud_risk"],
  "action": "none|manual-review|create-risk-task",
  "summary": "short grounded explanation",
  "confidence": 0.0
}
```

Invalid JSON or schema-invalid output falls back to deterministic governed rules. It is not counted as a real local LLM pass.

## Evidence Fields

Runtime and evidence bundles now record:

- `requestedLlmProvider`;
- `effectiveLlmProvider`;
- `llmGrounded`;
- `llmFallbackReason`;
- `llmOutputHash`.

## Status Endpoint

`GET /internal/agent-rag/ready` and dense health output now include `llm` status. The status masks local user home paths and does not expose model weights.

## Verification

Run:

```powershell
D:\anaconda\envs\torchtest-phase3a3-tf4\python.exe ai-service\scripts\readiness\run_agent_rag_phase4_local_llm_gate.py
```

Expected markers:

- `AGENT_RAG_LOCAL_LLM_OPTIONAL_PROVIDER_PASS`
- `AGENT_RAG_LOCAL_LLM_GROUNDED_CONTEXT_PASS`
- `AGENT_RAG_LOCAL_LLM_FALLBACK_BOUNDARY_PASS`
- `AGENT_RAG_PHASE4_LOCAL_LLM_GATE_PASS`

Current boundary:

```text
REAL_LLM_QUALITY_NOT_VERIFIED
NO_FAKE_REAL_LLM_PASS
ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED
```
