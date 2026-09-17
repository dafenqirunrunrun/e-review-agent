# Fast Eligibility Runtime Report

## Result

`STEP21_5_RUNTIME_GATE = PASS`

## Live Chain

`Admin API -> AI Service -> Intent Router -> frozen Fast Eligibility policy -> Fast or baseline chain`

- Runtime cases: `8`
- Fast / baseline: `3 / 5`
- Runtime Fast activation: `37.50%`
- High-risk Fast: `0`
- Safety Fast: `0`
- API errors: `0`
- Baseline/Fast decision mismatches: `0`

## Latency Pair

- Baseline median / P95: `80.055 / 101.675 ms`
- Fast median / P95: `69.774 / 84.591 ms`
- Median reduction: `12.84%`

## Safety And Isolation

- Checks: `21/21`
- Failed checks: `[]`
- Fixture cleanup completed: `true`
- Frozen benchmark executed: `false`
- Router, Safety Gate, RAG and frozen Fast policy modified: `false`
- Raw review text persisted in this artifact: `false`
- Rollback: set `E_REVIEW_FAST_ELIGIBILITY_RUNTIME_ENABLED=false` and restart AI Service.

## Interpretation

The Fast path is admitted only for requests already classified as low-touch with no risk hints and no image. All other requests retain the existing baseline workflow.
