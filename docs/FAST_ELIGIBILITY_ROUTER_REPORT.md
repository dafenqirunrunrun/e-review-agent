# Fast Eligibility Router Report

## Scope

Step 21.3H evaluates a deterministic FAST allowlist. LONG is the default route. No model, training, Frozen benchmark, Long Analysis execution, external API, or runtime Router modification is involved.

## Policy Freeze

Train64: `{"falseEscalationRate": 0.555556, "falseFast": 0, "fastCoverage": 0.25, "fastPrecision": 1.0, "highRiskFalseFast": 0, "longAnalysisRate": 0.75, "longRecall": 1.0, "safetyFalseFast": 0}`
Dev16: `{"falseEscalationRate": 0.555556, "falseFast": 0, "fastCoverage": 0.25, "fastPrecision": 1.0, "highRiskFalseFast": 0, "longAnalysisRate": 0.75, "longRecall": 1.0, "safetyFalseFast": 0}`
Policy hash: `3F39478C3E834A27BC83BDE6D27FF57C5846FBC62CD8B6B4BDC572A0A5D6CD79`

## Final Evaluation

Validation comparison: `{"currentRuleRouter": {"falseEscalationRate": 0.068966, "falseFast": 8, "fastCoverage": 0.875, "fastPrecision": 0.771429, "highRiskFalseFast": 8, "longAnalysisRate": 0.125, "longRecall": 0.272727, "safetyFalseFast": 8}, "fastEligibilityGate": {"falseEscalationRate": 0.62069, "falseFast": 0, "fastCoverage": 0.275, "fastPrecision": 1.0, "highRiskFalseFast": 0, "longAnalysisRate": 0.725, "longRecall": 1.0, "safetyFalseFast": 0}, "setfitBinaryRouter": {"falseEscalationRate": 0.310345, "falseFast": 3, "fastCoverage": 0.575, "fastPrecision": 0.869565, "highRiskFalseFast": 3, "longAnalysisRate": 0.42500000000000004, "longRecall": 0.727273, "safetyFalseFast": 3}}`
Boundary comparison: `{"currentRuleRouter": {"falseEscalationRate": 0.727273, "falseFast": 30, "fastCoverage": 0.55, "fastPrecision": 0.090909, "highRiskFalseFast": 27, "longAnalysisRate": 0.44999999999999996, "longRecall": 0.387755, "safetyFalseFast": 27}, "fastEligibilityGate": {"falseEscalationRate": 1.0, "falseFast": 0, "fastCoverage": 0.0, "fastPrecision": 0.0, "highRiskFalseFast": 0, "longAnalysisRate": 1.0, "longRecall": 1.0, "safetyFalseFast": 0}, "setfitBinaryRouter": {"falseEscalationRate": 1.0, "falseFast": 0, "fastCoverage": 0.0, "fastPrecision": 0.0, "highRiskFalseFast": 0, "longAnalysisRate": 1.0, "longRecall": 1.0, "safetyFalseFast": 0}}`
Boundary abstention: `{"captured": 5, "rate": 1.0, "targetCount": 5}`
Boundary hard negative: `{"caseCount": 15, "falseEscalationCount": 11, "falseEscalationRate": 1.0, "fastPrecision": 0.0, "fastRecall": 0.0, "fastTargetCount": 11, "predictedFastCount": 0}`

## Gates

`STEP21_3H_GATE = PASS`
`FAST_ELIGIBILITY_CANDIDATE_GATE = PASS`
`NEXT_RECOMMENDATION = FAST_ELIGIBILITY_SHADOW_MODE`
