# V2.2 Phase 8.8 Reranker Root Cause Decision

## Decision

- Decision: `ROOT_CAUSE_UNRESOLVED`
- Primary root cause: `MULTIPLE_CONTRIBUTING_FACTORS`
- Recoverable: `False`
- New holdout required: `True`
- Batch deterministic: `True`

## Metrics

| Path | overall nDCG@5 | overall MRR | semantic nDCG@5 | semantic MRR | severe regressions |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current real representation | 0.16823856851913252 | 0.2277027027027027 | 0.16227097958233325 | 0.22291666666666665 | 20 |
| Best diagnostic representation | 0.20403037751759875 | 0.2693693693693693 | 0.2077800224285421 | 0.26875 | 18 |
| Deterministic baseline | 0.35408337748729846 | 0.5342342342342342 | 0.27968725219107865 | 0.5666666666666667 | 0 |

## Boundary

The consumed 74-case diagnostic set cannot verify the model. A recovery experiment, if justified, requires a new unseen answerable holdout before `MODEL_RERANKER_VERIFIED` can be considered.
