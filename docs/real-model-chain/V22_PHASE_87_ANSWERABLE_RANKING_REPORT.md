# V2.2 Phase 8.7 Answerable Ranking Report

## Candidate Pool

- Candidate pool hash: `90afa384d48974e333966edbe67b0a66fe7d0b1dd1e851ec71dbeb690748bc0c`
- Query count: `174`
- Candidate count: `1392`
- Expired candidates: `0`
- Inactive candidates: `0`
- Tenant mismatches: `0`
- Status: `PASS`

## Answerable-Only Ranking

- Decision: `ANSWERABLE_RANKING_REGRESSION`
- Retrieval-eligible answerable cases: `74`
- Retrieval-missed answerable cases: `90`
- Real runtime executions: `74`
- Tenant violations: `0`
- Expired evidence accepted: `0`
- Identity mapping errors: `0`

## Metrics

- Deterministic semantic nDCG@5: `0.27968725219107865`
- Real semantic nDCG@5: `0.16227097958233325`
- Deterministic semantic MRR: `0.5666666666666667`
- Real semantic MRR: `0.22291666666666665`
- Deterministic overall nDCG@5: `0.35408337748729846`
- Real overall nDCG@5: `0.16823856851913252`
- Deterministic overall MRR: `0.5342342342342342`
- Real overall MRR: `0.2277027027027027`

## Boundary

If the decision is not `ANSWERABLE_RANKING_IMPROVED`, balanced answerability benchmark v2 and runtime policy integration remain blocked.
