# V2.3 Phase 9.2 Execution Status

Status: `BLOCKED_BEFORE_RUNTIME_INTEGRATION`

## What Was Fixed

The retrieval metric contract was corrected first. Raw Union Oracle, Budgeted Union, and RRF are now separated, and answerable recall/coverage no longer mixes no-answer cases. This resolved the impossible baseline contradiction where Dense Top-100 appeared higher than the reported Union Oracle Top-100.

## What Was Optimized

Calibration searched bounded candidate budgets and a limited weighted RRF set on the calibration split only. The selected candidate configuration was:

```text
bm25RetrieveK = 20
denseRetrieveK = 100
rrfRankWindow = 100
postFusionCandidateK = 20
maximumFinalK = 5
bm25Weight = 0.75
denseWeight = 1.25
allowBackfill = false
```

Calibration improved `Coverage@20` from the corrected baseline `0.579167` to `0.700000`.

## Held-Out Evaluation Result

The one-shot evaluation did not qualify the configuration for runtime integration:

```text
baseline Evaluation Coverage@20 = 0.520000
selected Evaluation Coverage@20 = 0.550000
absolute improvement = 0.030000
required improvement = 0.080000

selected Oracle Capture@SelectedK = 0.572917
required Oracle Capture@SelectedK = 0.950000
```

Ranking quality and resource checks were not the blocker:

```text
deterministic nDCG@5 improved from 0.133993 to 0.160503
deterministic MRR improved from 0.106000 to 0.134833
P95 latency ratio = 1.036245
tenant violations = 0
expired evidence accepted = 0
low-score backfill = 0
```

## Engineering Decision

Runtime integration is intentionally skipped. Evaluation results are not used for retuning in this phase, so Phase 9.2 closes as an auditable unresolved qualification rather than a forced runtime change.

## Resume-Ready Summary

Identified that deeper retrievers had recoverable relevant evidence, corrected an invalid retrieval metric definition, then performed bounded candidate-budget and RRF-window optimization. The calibration configuration improved recall on the tuning split, but held-out qualification exposed insufficient oracle capture, so runtime rollout was blocked by design. This demonstrates experiment discipline, leakage prevention, and production-style gatekeeping.

## Remaining Work

Next retrieval work should target the root cause that simple RRF budget expansion cannot solve:

```text
query rewriting or query2doc
chunking/parent-child retrieval
BGE-M3 sparse or multi-vector retrieval
reranker model availability and quality qualification
```

The following boundaries remain:

```text
NO_PUSH
NO_TAG
NO_RELEASE
NO_PUBLIC_REPO_CHANGES
ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED
```
