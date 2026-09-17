# v2.2 Real LLM Runtime Integration

## Scope

This document records the formal runtime integration of the local Qwen3 analysis
provider. It is not a quality qualification report and does not close
`REAL_LLM_QUALITY_NOT_VERIFIED`.

## Model

| Field | Value |
| --- | --- |
| Model ID | `Qwen/Qwen3-1.7B` |
| Revision | `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` |
| Asset source | repo-external v2.2 asset manifest |
| Runtime | Transformers local model |
| Device | CUDA |
| Sampling | disabled |
| Raw model output persisted | No |
| Full prompt persisted | No |

## Formal Runtime Path

```text
AgentRagRuntime
-> AgentRagLlmDecider
-> LocalQwenTransformersProvider
-> LocalQwenRuntime
-> AutoModelForCausalLM.generate
```

The model is cached by `LocalQwenRuntime` and is not reloaded for each request
when the resolved model source is unchanged.

## Evidence Fields

The formal runtime now emits lightweight evidence fields:

```text
requestedAnalysisProvider
effectiveAnalysisProvider
llmModelId
llmRevision
llmFingerprint
promptVersion
promptFingerprint
llmInputTokens
llmOutputTokens
llmDurationMs
structuredOutputValid
groundingStatus
abstained
uncertaintyReason
requiresHumanReview
llmFallbackUsed
llmFallbackReason
llmOutputHash
```

Absolute model paths, Hugging Face cache paths, full prompts and full raw model
outputs are intentionally excluded from persisted evidence.

## Verification

Targeted tests executed in the isolated v2.2 runtime environment:

```text
python -m pytest -ra ai-service/tests/test_v200_agent_rag_phase4_local_llm.py
6 passed, 1 skipped

python -m pytest -ra -m real_llm_runtime
1 passed, 503 deselected
```

The `real_llm_runtime` marker executes through `AgentRagRuntime`; it is not a
standalone smoke script.

## Remaining Gates

The following remain open:

```text
REAL_LLM_QUALITY_NOT_VERIFIED
AGENT_RAG_V22_REAL_MODEL_E2E pending
1800-second real model chain soak pending
```
