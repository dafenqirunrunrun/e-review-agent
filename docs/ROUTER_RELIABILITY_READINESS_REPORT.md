# Router Reliability Readiness Report

## Goal

Evaluate whether the current pre-expensive-model runtime signals can support ordinal HIGH / MEDIUM / LOW / ABSTAIN reliability tiers. These tiers are routing reliability bands, not calibrated probabilities.

## Dataset Status

- Calibration: 120 cases, SHA `DB3B4B9692EBB08B1A4A0CC45715084369AEE4BD571BCBAED6FDBF297F6A48A3`.
- Boundary Challenge: 60 cases, SHA `5472C19987A23F57BF121321D47958C1D5ED0344615E12C9714CD26A4A021730`.
- Frozen benchmark remained read-only, SHA `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`.
- Semantic status: `PASS_WITH_SINGLE_JUDGE_LIMITATION`; this is a single-judge demo candidate, not human gold.

## Runtime Signal Inventory

Inventory gate: `PASS`. The analysis called `IntentRouterAgent._route_with_rules + RiskSeverityEvaluator` and did not call RAG, FAISS, embeddings, reflection, an LLM, or the complete workflow.

Available signals: `intentType`, `reasonCodes`, `requiresEvidence`, `matchedRiskSignals`, `routeCandidate`, `rawConfidence`, `safetyGateLatencyMs`, `matchedRuleCount`, `safetyGateTriggered`, `predictedRiskCount`, `predictedSeverity`.

## Leakage Audit

Leakage gate: `PASS`. Policy input/evaluation field overlap: `0`. Boundary data was evaluated only after P1 was frozen; Frozen Gold was hash-checked only.

## Calibration Fit / Validation Split

A deterministic multivariate split produced Fit `80` and Validation `40` cases using seed `step21.2.3-reliability-split-v1`.

## Cheap Router Baseline

Combined disposition-aware accuracy is `30.00%`; risk exact-match accuracy is `30.86%`; micro F1 is `0.3699`; macro F1 is `0.3246`.

## Raw Confidence Cardinality

The router emitted `3` unique values: `[0.68, 0.84, 0.88]`. Finding: `LOW_CARDINALITY_CONFIDENCE`. Raw confidence is therefore unsuitable as a probability claim.

## Slice Results

- explicit: cases `41`, exact accuracy `21.95%`, micro F1 `0.3158`.
- implicit: cases `105`, exact accuracy `40.00%`, micro F1 `0.4000`.
- mixed: cases `34`, exact accuracy `14.71%`, micro F1 `0.3559`.
- multiRisk: cases `48`, exact accuracy `0.00%`, micro F1 `0.2791`.
- hard: cases `86`, exact accuracy `12.35%`, micro F1 `0.2931`.
- normalReview: cases `49`, exact accuracy `85.71%`, micro F1 `0.8155`.
- abstentionTarget: cases `5`, exact accuracy `0.00%`, micro F1 `0.0000`.

## Reliability Policy Candidates

P0 uses confidence bands only. P1 uses runtime-safe rule signals and deliberately emits no HIGH tier because no qualifying segment exists. P2 is a simulation overlay; it does not change runtime behavior. P1 was selected on Fit and checked once on Validation without a policy adjustment.

## HIGH / MEDIUM / LOW / ABSTAIN

- HIGH: count `0`, coverage `0.00%`, accuracy `N/A`, material safety errors `0`.
- MEDIUM: count `3`, coverage `7.50%`, accuracy `100.00%`, material safety errors `0`.
- LOW: count `37`, coverage `92.50%`, accuracy `40.54%`, material safety errors `10`.
- ABSTAIN: count `0`, coverage `0.00%`, accuracy `N/A`, material safety errors `0`.

## Error Capture

Validation LOW + ABSTAIN captured `22/22` errors (`100.00%`).

## Material Safety Errors

The selected P1 policy emitted no HIGH cases, so HIGH material safety errors are `0`; this is conservative containment, not evidence of HIGH-tier quality. Combined baseline material misses: `77`.

## Boundary Challenge Validation

Boundary fast-path count is `0` with `0` material safety errors. Abstention targets routed to strict/human: `5/5`.

## Fast Path Simulation

Validation fast-path count is `0`, coverage `0.00%`, accuracy `N/A`. The fast-path acceptance gate is `False`.

## Current Cheap Router Readiness

Gate: `FAIL`. Reason: `RELIABILITY_SIGNAL_NOT_SEPARABLE`. The current signals do not support a HIGH tier with both >=95% accuracy and >=15% coverage, nor a >=10% safe fast path.

## Offline Model Router Benchmark Readiness

Gate: `PASS`. Dataset immutability, split, signal contract, evaluator, and safety checks are ready for a later offline model-router benchmark.

## Limitations

- Labels are semantically reviewed by a single judge and are not human gold.
- Only three raw confidence values were observed.
- Text-only fixtures do not supply production rating or image signals.
- An empty HIGH tier prevents false assurance but also prevents fast-path deployment.
- P2 is an offline simulation and does not modify production routing.

## Next Step

Stop at Step 21.2.3. A later, separately approved step may benchmark an offline model router against this frozen harness; no runtime model routing or calibration change is made here.
