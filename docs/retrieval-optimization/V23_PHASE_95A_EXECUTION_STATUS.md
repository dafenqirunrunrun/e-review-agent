# V2.3 Phase 9.5A Execution Status

## Gates

- Sparse route closure: `PASS`
- Parent-child hierarchy: `PASS`
- Parent index: `PASS`
- Calibration: `BLOCKED`
- Resource: `PASS`
- Default regression: `BLOCKED_BY_EXISTING_BASE_ENV_DEPENDENCY_FAILURES`
- Phase 9.5A: `E_REVIEW_V23_PHASE_95A_BLOCKED`
- `PHASE_95B_PARENT_CHILD_EVALUATION_ALLOWED=false`

## Resource

- Total retrieval P95 ms: `8.260147`
- Index size ratio: `1.06`
- Dense runtime boundary: `REAL_DENSE_RUNTIME_NOT_AVAILABLE_IN_DEFAULT_ENVIRONMENT`

## Test Evidence

- Targeted parent-child tests: `8 passed`
- `python -m pip check`: failed due existing base Conda package conflicts
- `python -m pytest -ra`: `529 passed, 21 skipped, 12 failed`; failures are existing FAISS/torch dependency and v1.8 failure-injection artifact issues, not parent-child tests
- `python -m pytest -ra -m real_dense`: `1 passed, 7 skipped, 8 selected`; recorded as `REAL_DENSE_SELECTED_TEST_ASSET_DISCOVERY_PARTIAL`

## Resume Record

Problem: Dense Top100 coverage was high, but operational Top20 candidate capture remained weak and Sparse proved unstable.

Action: Closed the Sparse route with a 24-run evidence matrix, then built deterministic Document/Section/Chunk parent-child retrieval over the calibration split.

Result: Hierarchy and parent index governance passed. Calibration did not qualify for held-out Evaluation because the selected configuration failed one or more quality/runtime gates.

Decision: Phase 9.5B remains blocked until a materially better retrieval hypothesis is qualified without reading Evaluation or Challenge.
