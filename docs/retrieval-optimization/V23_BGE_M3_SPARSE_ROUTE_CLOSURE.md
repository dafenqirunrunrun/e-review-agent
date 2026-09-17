# V2.3 BGE-M3 Sparse Route Closure

## Scope

This document closes the v2.3 BGE-M3 Sparse route for the current E-Review Agent runtime qualification. It is an evidence-preserving route decision, not a global claim that BGE-M3 Sparse or FlagEmbedding is broken.

## Evidence Boundary

- Source commit: `c230fffd`
- Full corpus eligible chunk count: `153`
- Precision stability matrix: `24` completed runs
- Runtime smoke: verified in the isolated environment
- Sparse retrieval/index qualification: not accepted for v2.3 runtime

The closure references existing artifacts by SHA-256 and does not overwrite the original PSQ/RCA/DQA evidence.

## Formal Status

- `BGE_M3_SPARSE_RUNTIME_VERIFIED`
- `BGE_M3_SPARSE_ENCODING_NOT_REPRODUCIBLE`
- `BGE_M3_SPARSE_ROUTE_REJECTED_FOR_V2_3`

## Decision

`NO_STABLE_SPARSE_ENCODING_CONFIGURATION`

The 24-run matrix covered precision, batch size, invocation path, and fresh-process repeatability. The route remained unstable across those axes, so the following are frozen as false:

- `SPARSE_INDEX_REBUILD_ALLOWED`
- `SPARSE_RETRIEVAL_CALIBRATION_ALLOWED`
- `PHASE_94C_THREE_WAY_FUSION_ALLOWED`
- v2.3 runtime sparse integration

## Resume Evidence

Problem: Dense retrieval had high Top100 coverage, but candidate capture at smaller operational budgets remained insufficient. Sparse was evaluated as a possible second route.

Action: Built a 24-run sparse encoding stability matrix over precision, batch size, invocation path, and fresh process repeatability.

Result: Runtime was verified, but no stable sparse encoding configuration was found. The route was blocked by governance gates instead of being promoted into the Agent runtime.

Decision: Freeze Sparse for v2.3 and evaluate deterministic Parent-Child hierarchical retrieval as the next controlled hypothesis.
