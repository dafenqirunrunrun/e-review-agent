# V2.2 Real Reranker Regression Diagnosis

## Frozen Baseline

- Model: `BAAI/bge-reranker-v2-m3`
- Revision: `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`
- Configuration: candidateK `8`, finalK `5`, batch `8`, maxLength `384`, dtype `fp16`
- Decision: `AGENT_RAG_V22_REAL_RERANKER_QUALITY_REGRESSION`
- Boundary: `MODEL_RERANKER_NOT_VERIFIED`

## Quality Metrics

| Metric | Deterministic | Real Reranker |
| --- | ---: | ---: |
| Semantic nDCG@5 | 0.04281830320718995 | 0.022011869324643295 |
| Semantic MRR | 0.07982456140350877 | 0.03684210526315789 |
| Overall nDCG@5 | 0.15882429684329197 | 0.0713659517421812 |
| Overall MRR | 0.23224043715846993 | 0.09453551912568306 |

Safety counters: tenant violations `0`, inactive leaks `0`, expired leaks `3`, false evidence `35`.

## Harness Audit

- Status: `PASS_WITH_TEST_GAPS`
- Score descending sort: `True`
- Stable tie-break: `True`
- Fallback not counted as real: `True`
- Normalize order test present: `False`

## Case Analysis

- Case count: `122`
- Root-cause counts: `{"CANDIDATE_POOL_TOO_SMALL": 7, "SEMANTIC_MODEL_MISMATCH": 83, "UNKNOWN": 32}`

The case analysis intentionally omits full private text and raw model outputs. It is a safe diagnostic index for follow-up tests.
