# V2.2 Real Reranker Recovery Decision

## Decision

Phase 8.4 does not verify the real reranker quality gate.

- Decision token: `AGENT_RAG_V22_REAL_RERANKER_QUALITY_REGRESSION`
- Boundary: `MODEL_RERANKER_NOT_VERIFIED`
- Final real model chain status: `AGENT_RAG_V22_REAL_MODEL_CHAIN_BLOCKED`

## What Was Proven

The implementation-level checks passed:

- Score direction test passed: relevant passages rank above unrelated passages on the diagnostic set.
- FlagEmbedding and direct Transformers forward parity passed with Spearman rank correlation at the required threshold.
- Runtime sorting uses score descending, then original rank, then chunk id.
- Fallback results are not counted as real reranker executions.

This means the current blocker is not explained by an obvious score direction or wrapper parity bug.

## Why Calibration Recovery Is Blocked

The frozen evaluation requires `falseEvidenceCount = 0`. The observed failed evaluation has:

- No-answer cases: `7`
- finalK: `5`
- Expected false evidence when every no-answer query still returns topK: `35`
- Observed false evidence: `35`
- No-answer correct rejection: `0.0`

The current reranker runtime always returns the top ranked candidates and has no calibrated rejection threshold for no-answer cases. Therefore, dtype, batch size, max length, or candidateK alone cannot make `falseEvidenceCount` reach zero under the frozen safety rule.

The real reranker also remains below the deterministic baseline on semantic and overall metrics:

| Metric | Deterministic | Real Reranker |
| --- | ---: | ---: |
| Semantic nDCG@5 | 0.04281830320718995 | 0.022011869324643295 |
| Semantic MRR | 0.07982456140350877 | 0.03684210526315789 |
| Overall nDCG@5 | 0.15882429684329197 | 0.0713659517421812 |
| Overall MRR | 0.23224043715846993 | 0.09453551912568306 |

## Why We Do Not Continue Parameter Search

The evaluation split has already been observed. Returning to calibration to keep tuning after seeing the evaluation result would weaken the frozen benchmark protocol. The safe conclusion is to record the regression and keep the model-chain boundary blocked.

## Next Safe Change

A future phase may implement a separate calibrated no-answer/rejection policy using only calibration data. After freezing that policy, the project may run one evaluation pass and then rerun E2E plus 1800-second soak if the runtime behavior changes.

Until then, the default strict qualification remains:

```text
REAL_LLM_QUALITY_VERIFIED
AGENT_RAG_V22_REAL_RERANKER_RUNTIME_PASS
MODEL_RERANKER_NOT_VERIFIED
AGENT_RAG_V22_REAL_MODEL_CHAIN_BLOCKED
```
