# Hybrid Router Offline Simulation Report

## Scope

Step 21.3B simulates Rule Router as the primary classifier and frozen BGE-M3 + logistic heads as a semantic routing guard. It changes no runtime code, never merges or overwrites Rule labels, executes no Frozen cases, and calls no external API.

## Fit80 OOF Complementarity

Quadrants: `{"ruleCorrectBgeCorrect": 0, "ruleCorrectBgeWrong": 30, "ruleWrongBgeCorrect": 0, "ruleWrongBgeWrong": 50}`. Rule-error BGE disagreement rate: `1.0000`.

## Frozen Policy

Selected `H1_CONSENSUS_GUARD` with guard threshold `None` from Fit80 OOF only. OOF fast coverage `0.0000`, exact accuracy `0.0000`, material safety errors `0`.

## Validation

Fast `0` / `0.0000`, exact `0.0000`, safety errors `0`. Rule-error capture `1.0000`, multi-risk miss capture `1.0000`, material safety capture `1.0000`, false escalation `1.0000`.

## Boundary And Latency

Boundary fast/strict/human: `0/60/0`; fast safety errors `0`. Hybrid P50/P95 `28.4614/37.74515 ms`.

## Gates

- `hybridOofGate` = `PASS`
- `hybridSignalLeakageGate` = `PASS`
- `hybridPolicySelectionGate` = `PASS`
- `hybridValidationGate` = `PASS`
- `hybridErrorCaptureGate` = `PASS`
- `hybridSafetyGate` = `PASS`
- `hybridBoundaryGate` = `PASS`
- `hybridAbstentionGate` = `PASS`
- `hybridLatencyGate` = `PASS`
- `step21_3bGate` = `PASS`
- `hybridRouterCandidateGate` = `FAIL`

## Conclusion

`HYBRID_ROUTER_TOO_CONSERVATIVE`
