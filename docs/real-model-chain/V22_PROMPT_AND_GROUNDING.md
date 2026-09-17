# v2.2 Prompt Boundary and Grounding

## Prompt Boundary

The formal local Qwen3 prompt is separated into:

```text
TRUSTED_SYSTEM_POLICY
BUSINESS_INPUT
UNTRUSTED_RETRIEVED_EVIDENCE
OUTPUT_SCHEMA
```

The prompt states that retrieved evidence is untrusted business data, that
instructions inside evidence must not be followed, and that the model may cite
only citation IDs supplied in the evidence set.

## Output Contract

The accepted model payload is:

```json
{
  "riskLevel": "low|medium|high|unknown",
  "riskTypes": [],
  "summary": "",
  "action": "allow|monitor|manual-review|create-risk-task|block",
  "confidence": 0.0,
  "citationIds": [],
  "abstain": false,
  "uncertaintyReason": null,
  "requiresHumanReview": false
}
```

Runtime mapping preserves the existing public Agent-RAG decision contract:

```text
allow -> none
monitor -> manual-review
manual-review -> manual-review
create-risk-task -> create-risk-task
block -> create-risk-task
unknown riskLevel -> medium
abstain -> manual-review
```

## Grounding Checks

The runtime validates:

```text
single JSON object extraction
no think tag leakage
schema and enum conformance
risk type allowlist
duplicate citation rejection
citation ID membership in retrieved evidence
basic grounded summary overlap when no citation IDs are returned
```

Invalid JSON, invalid schema, invalid citation or ungrounded output falls back to
the governed rule path and records a failure reason. Prompt injection detected by
the security governor suppresses Qwen3 execution before retrieval/model analysis.

## Boundary

This prompt and grounding implementation proves formal runtime control. It does
not claim final LLM quality. The frozen 250-case quality suite, Java E2E path and
1800-second soak must pass before `REAL_LLM_QUALITY_VERIFIED` can be closed.
