# v2.1 Release Candidate Eligibility

## Decision

```text
RETAIN_FFD05F26_RC_BASELINE
```

## Reason

v2.1 qualification infrastructure is ready, but the blocker-closure branch did
not close all non-optional candidate gates.

Still open:

- `MODEL_RERANKER_NOT_VERIFIED`
- `REAL_LLM_QUALITY_NOT_VERIFIED`
- `VULNERABILITY_DATABASE_UNAVAILABLE`
- `LICENSE_REVIEW_REQUIRED`

## Regression Evidence

- Python default full regression: `488 passed, 12 skipped, 0 failed`
- Java full test: PASS
- Java package: PASS
- Admin build: PASS with existing warnings
- Customer H5 build: PASS with existing warnings
- Migration immutability: PASS
- Cross-platform checksum: PASS
- v2.0 RC compatibility: PASS
- v2.1 reproducibility gate: PASS
- 10K scale: PASS
- 100K scale: PASS
- Multi-process consistency: PASS

## Preserved Baselines

- v2.0 RC: `ffd05f2611cf2c7996a681fa0343778da73f7e50`
- v2.1 qualification infrastructure: `2d160578c381cd701f90cbcf57b4a682959a2988`

## Boundary

No push, tag or release was created. Candidate eligible does not equal
production ready, and this branch is not candidate eligible yet.
