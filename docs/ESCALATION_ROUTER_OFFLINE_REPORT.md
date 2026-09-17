# Escalation Router Offline Report

## Scope

Step 21.3C uses only cheap runtime signals to choose FAST_PATH or LONG_ANALYSIS. It does not execute Long Analysis, BGE, Qwen, RAG, Reflection, Workflow, Frozen Gold, or any external API, and it changes no runtime code.

## Signal And Policy

Selected `S0_MINIMAL` at threshold `2` from Fit80 only. Formula: `requiresEvidence +1; matchedRiskSignals>=1 +1; matchedRiskSignals>=2 +1`. Safety Gate is a hard LONG_ANALYSIS override.
Observed conflict/uncertain/ambiguous reason codes: `[]`; none were invented. Raw confidence remains an ordinal low-cardinality signal, not a probability.

## Fit And Validation

Fit fast coverage `0.7625`, exact `0.393443`, safety errors `18`, rule-error capture `0.2600`.
Validation fast `35/40` (`0.8750`), exact `0.428571`, micro F1 `0.394737`, safety errors `8`. Long-analysis rate `0.1250`; false escalation `0.1667`.

## Boundary And Latency

Boundary fast/long `33/27`, fast safety errors `27`. Hard-negative fast coverage `0.2667`, accuracy `0.75`.
Cheap gate P50/P95 `0.0363/0.063905 ms`; long-analysis rate is a compute-cost proxy, not an API-cost claim.

## Gates

- `escalationSignalGate` = `PASS`
- `escalationPolicySelectionGate` = `PASS`
- `escalationValidationGate` = `PASS`
- `escalationSafetyGate` = `FAIL`
- `escalationBoundaryGate` = `PASS`
- `escalationLatencyGate` = `PASS`
- `escalationAbstentionGate` = `FAIL`
- `step21_3cGate` = `PASS`
- `escalationRouterCandidateGate` = `FAIL`

## Conclusion

`SAFETY_LEAK`
