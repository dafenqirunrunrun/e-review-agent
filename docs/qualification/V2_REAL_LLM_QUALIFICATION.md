# v2.1 Real Local LLM Qualification

## Objective

This module evaluates whether a real local generative LLM can be qualified for
grounded, schema-valid E-Review Agent decisions. It does not modify the locked
v2.0 RC baseline at `ffd05f26`.

## Existing Implementation Audit

The repository already contains a governed local LLM path:

- `ai-service/app/agent_rag/llm_decider.py` supports
  `local_qwen3_transformers`.
- `ai-service/app/llm/config.py` maps local Qwen aliases to
  `local_qwen3_transformers`.
- `ai-service/app/llm/service.py` creates the local transformers tool when that
  provider is explicitly configured.
- Existing readiness scripts retain `REAL_LLM_QUALITY_NOT_VERIFIED` unless a
  real local model path and quality evidence are available.

No LLM provider rewrite was performed in this qualification step.

## Asset Status

The offline model asset audit produced:

- Asset type: `llm`
- Environment variable: `AGENT_LLM_MODEL_PATH`
- Available: `false`
- Blocker: `ENV_PATH_NOT_SET`
- Asset fingerprint: `null`

Because the required model path is not configured, the campaign must not attempt
runtime loading, generation, schema-quality measurement, safety gate promotion,
or default-provider promotion.

## Test Result

Executed:

```text
python -m pytest -ra -m real_llm
```

Result:

```text
0 selected, 499 deselected
```

The command returned a non-zero pytest exit because no test is currently marked
`real_llm` in this worktree. This is recorded as a test coverage gap, not as a
model runtime pass.

## Decision

```text
AGENT_RAG_REAL_LLM_BLOCKED
REAL_LLM_QUALITY_NOT_VERIFIED
```

The rule analysis path remains the default path. This is a truthful
qualification blocker, not a failure of the v2.0 RC baseline.
