# Safety Guard Router Report

## Scope

Step 21.3G evaluates one frozen open-source safety model, both alone and with an isolated business-rule layer. No training, Frozen benchmark, runtime Router change, Long Analysis, or external inference API call occurred.

## Model

`DuoGuard/DuoGuard-0.5B` revision `44396C3576FDD5F844C64615489CDBB5B3B3F3CE`, `494043520` parameters, `Apache-2.0`, `cuda` `bfloat16`.
Safety latency: `{"p50Ms": 22.31515, "p95Ms": 27.2812, "p99Ms": 31.591051}`. End-to-end: `{"p50Ms": 22.86505, "p95Ms": 28.424175, "p99Ms": 33.096949}`.

## Results

Safety model only Validation: `{"falseEscalationRate": 0.0, "falseFast": 10, "fastCoverage": 0.975, "fastPrecision": 0.74359, "highRiskFalseFast": 9, "longAnalysisRate": 0.025, "longRecall": 0.090909, "safetyFalseFast": 9}`
Safety model plus business rules Validation: `{"falseEscalationRate": 0.034483, "falseFast": 7, "fastCoverage": 0.875, "fastPrecision": 0.8, "highRiskFalseFast": 7, "longAnalysisRate": 0.125, "longRecall": 0.363636, "safetyFalseFast": 7}`
Safety model plus business rules Boundary: `{"falseEscalationRate": 0.363636, "falseFast": 33, "fastCoverage": 0.666667, "fastPrecision": 0.175, "highRiskFalseFast": 33, "longAnalysisRate": 0.333333, "longRecall": 0.326531, "safetyFalseFast": 33}`
Hard negative: `{"caseCount": 15, "falseEscalationCount": 4, "falseEscalationRate": 0.363636, "fastCoverage": 0.533333}`
Abstention: `{"captured": 5, "rate": 1.0, "targetCount": 5}`

## Gates

`STEP21_3G_GATE = PASS`
`SAFETY_GUARD_ROUTER_CANDIDATE_GATE = FAIL_SAFETY`
`NEXT_RECOMMENDATION = SAFETY_GUARD_INSUFFICIENT_FOR_BUSINESS_RISK_ROUTING`
