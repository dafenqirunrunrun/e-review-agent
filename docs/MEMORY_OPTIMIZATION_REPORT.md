# Step 19.1 Memory Optimization Report

## Scope

Step 19.1 adds an in-process, per-review `GovernanceMemory`. It is not a database and never carries information from one review to another. It does not alter the Intent Router, Safety Gate, Policy Retriever, EvidenceAgent, ReflectionAgent, or human-review state machine.

## Memory Model

The structured memory schema is:

```json
{
  "riskTypes": ["fake_review"],
  "evidenceIds": ["E1", "E3"],
  "reflectionStatus": "supported",
  "humanDecision": "pending",
  "workflowState": "finalized"
}
```

Each iteration also records `goal`, `confirmedFacts`, `evidenceUsed`, `unresolvedIssues`, and `nextAction`. The context controller prioritizes structured state, then iteration summaries, then the most recent two turns. Older full turns are excluded before the latest information is dropped. Defaults: `recentTurns=2`, `maxContextTokens=800`.

## Context Reduction

The benchmark used a real strict review flow with policy citations. The complete workflow trace, including bounded evidence rows, was the pre-compression baseline.

| Metric | Result |
| --- | ---: |
| Full trace context estimate | 2,767 tokens |
| Budgeted memory context estimate | 199 tokens |
| Reduction | 92.81% |
| Configured context budget | 800 tokens |

The token estimator is dependency-free and deterministic: CJK characters count as one token estimate and other characters use a four-character estimate. It is a capacity guard, not a tokenizer billing claim.

## Decision Consistency And Latency

The same prewarmed, cache-disabled strict review produced the same `human_review` decision, risk types (`fake_review`, `rating_manipulation`, `review_suppression`), evidence status (`supported`), and human-review requirement with Memory disabled and enabled.

| Mode | Workflow latency |
| --- | ---: |
| Memory disabled, warm | 1,217.50 ms |
| Memory enabled, warm | 1,157.62 ms |

The observed 59.88 ms difference is normal local variance, not a claimed performance gain. The default Planner/Execution path is deterministic and does not send an LLM prompt, so LLM input latency is not applicable in this stage. The memory package prepares a bounded context for a future LLM-backed reasoning node without changing current business behavior.

## Regression

- Memory window and priority test: passed.
- Memory on/off decision consistency test: passed.
- Policy RAG, Reflection, review API, and Intent Safety targeted regression: 35 passed.
- Frozen quality benchmark after service restart: PASS. Gold SHA is unchanged; Hybrid Recall@1/@5 is 0.9667/0.9667, Risk F1 is 0.7677, high-risk auto-pass count is 0, API errors are 0, and requested/actual retrieval mode is hybrid/hybrid.

## Limitations

This is short-term workflow memory, not cross-review learning. It does not replace Human Review audit records, policy evidence snapshots, or the existing database trace. There is no LLM planner prompt in the current production path, so the memory context is exposed as bounded structured workflow state rather than being silently injected into decision logic.
