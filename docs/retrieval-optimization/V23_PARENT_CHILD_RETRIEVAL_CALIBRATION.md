# V2.3 Parent-Child Retrieval Calibration

## Boundary

- Split used: Benchmark v2 Calibration only
- Answerable cases: `120`
- No-answer cases: `30`
- Configuration count: `48` / `48`
- Evaluation and Challenge splits: frozen and unread

## Parent Representation

| Representation | HitRate@5 | HitRate@10 | HitRate@20 |
|---|---:|---:|---:|
| P1 | 0.8 | 0.875 | 1.0 |
| P2 | 0.8 | 0.875 | 1.0 |

## Flat Baseline Versus Selected Parent-Child

- Flat Coverage@20: `0.7`
- Selected Coverage@20: `0.766667`
- Absolute lift: `0.066667`
- Flat MRR: `0.196237`
- Selected MRR: `0.204649`
- Flat nDCG@5: `0.190482`
- Selected nDCG@5: `0.204384`

## Decision

`NO_VALID_PARENT_CHILD_CONFIGURATION`

Failure reasons: `REAL_DENSE_RUNTIME_NOT_AVAILABLE_IN_DEFAULT_ENVIRONMENT`
