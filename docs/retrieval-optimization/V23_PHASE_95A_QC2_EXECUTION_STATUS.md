# V2.3 Phase 9.5A-QC2 Execution Status

Decision: `E_REVIEW_V23_PHASE_95A_QC2_PASS`

`PHASE_95B_PARENT_CHILD_EVALUATION_ALLOWED=true`

Blocking checks: `none`

## Resume Evidence

Problem: Parent-Child calibration had a measurable lift, but previous artifacts did not prove that candidate sets and ranked evidence were reproducible across processes.

Action: QC2 added canonical SHA-256 hashes for parent candidates, hierarchical candidates, flat candidates, union candidates, deterministic ranking and final evidence, then compared two fresh calibration runs and index rebuild fingerprints.

Result: Ranking and index parity are recorded. Held-out Evaluation remains blocked until three-layer full regression and detached verification are closed.
