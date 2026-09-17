# Binary Escalation Router Report

## Scope

Step 21.3D evaluates a frozen local BGE-M3 encoder plus one binary logistic head. It is offline-only and does not change the runtime Router, Safety Gate, Agent workflow, RAG, datasets, or Frozen benchmark.

## Target And Split

Fit FAST/LONG `45/35`; Validation `29/11`; Boundary `11/49`.
Threshold `0.3` was selected only on Fit-internal Dev16 using safety-first ordering.

## Validation

| Metric | Cheap rule | BGE binary |
| --- | ---: | ---: |
| LONG recall | 0.2727 | 1.0000 |
| FAST precision | 0.7714 | 1.0000 |
| FAST coverage | 0.8750 | 0.0500 |
| False fast | 8 | 0 |
| High-risk false fast | 8 | 0 |
| Material-safety false fast | 8 | 0 |

## Boundary And Latency

Boundary LONG recall `1.0000`, FAST precision `0.0000`, false fast `0`, abstention capture `5/5`, hard-negative FAST recall `0.0000`.
Warm batch-1 end-to-end P50/P95 `29.614/54.793905 ms`.

## Gates

`STEP21_3D_GATE = PASS`
`BINARY_ROUTER_CANDIDATE_GATE = FAIL`
`NEXT_RECOMMENDATION = SETFIT_BINARY_CLASSIFIER_EVALUATION`
