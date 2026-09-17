# SetFit Conservative Policy Report

## Scope

Step 21.3F evaluates fixed thresholds against the frozen Step 21.3E SetFit model. No model training, dataset modification, Frozen benchmark, runtime change, Qwen call, or external API call occurred.

The score is `longRequiredScore`; therefore, a higher threshold makes LONG_REQUIRED harder to trigger and is less conservative under the frozen decision rule.

## Dev16 Threshold Sweep

| Threshold | FAST | LONG | FAST coverage | LONG recall | FAST precision | High-risk false fast | Safety false fast |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.50 | 10 | 6 | 0.6250 | 0.5714 | 0.7000 | 3 | 2 |
| 0.60 | 11 | 5 | 0.6875 | 0.4286 | 0.6364 | 4 | 2 |
| 0.70 | 11 | 5 | 0.6875 | 0.4286 | 0.6364 | 4 | 2 |
| 0.80 | 13 | 3 | 0.8125 | 0.4286 | 0.6923 | 4 | 2 |
| 0.90 | 15 | 1 | 0.9375 | 0.1429 | 0.6000 | 6 | 4 |

Selected threshold: `0.5`. Safety-feasible candidate found: `false`.

## Final Evaluation

Validation: `{"caseCount": 40, "falseEscalationCount": 9, "falseEscalationRate": 0.310345, "falseFastCount": 3, "falseFastRate": 0.272727, "fastCount": 23, "fastCoverage": 0.575, "fastPrecision": 0.869565, "highRiskFalseFastCount": 3, "longCount": 17, "longRate": 0.425, "longRequiredRecall": 0.727273, "materialSafetyFalseFastCount": 3}`
Boundary: `{"caseCount": 60, "falseEscalationCount": 11, "falseEscalationRate": 1.0, "falseFastCount": 0, "falseFastRate": 0.0, "fastCount": 0, "fastCoverage": 0.0, "fastPrecision": 0.0, "highRiskFalseFastCount": 0, "longCount": 60, "longRate": 1.0, "longRequiredRecall": 1.0, "materialSafetyFalseFastCount": 0}`
Abstention: `{"captured": 5, "rate": 1.0, "targetCount": 5}`
Hard negative: `{"caseCount": 15, "falseEscalationCount": 11, "falseEscalationRate": 1.0, "fastPrecision": 0.0, "fastRecall": 0.0, "fastTargetCount": 11, "predictedFastCount": 0}`

## Gates

`STEP21_3F_GATE = PASS`
`SETFIT_ROUTER_CANDIDATE_GATE = FAIL_SAFETY`
`NEXT_RECOMMENDATION = SETFIT_BINARY_ROUTER_UNSAFE`
