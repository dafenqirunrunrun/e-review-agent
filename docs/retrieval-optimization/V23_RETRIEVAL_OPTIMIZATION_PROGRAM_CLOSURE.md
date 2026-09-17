# V2.3 Retrieval Optimization Program Closure

## Decision

- Program closed: `True`
- New qualified runtime candidates: `0`
- Runtime promotion: `False`
- Reference baseline retained: `True`
- Next program: `v2.4-agent-productionization`

## Lessons Learned

Calibration lift is not enough for runtime promotion. Sparse runtime can be verified but still rejected if encoding is not reproducible. Parent-aware fusion showed local value but failed held-out generalization. Challenge remains unconsumed.

## Future Benchmark v3 Preconditions

A future v3 requires a new knowledge snapshot, new query source or user scenarios, new annotation workflow, a genuinely new retrieval hypothesis, stronger case-family isolation and at least 50 percent non-rewritten cases.
