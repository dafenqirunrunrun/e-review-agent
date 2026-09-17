# Fast Eligibility Shadow Report

## Scope

The frozen Step 21.3H policy is evaluated after the current route is known. The evaluator records metadata only and never executes either candidate chain or changes the review response.

## Metrics

- Observed requests: `2368`
- Long Analysis Reduction: `27.36%`
- Potential Cost Saving: `27.36%` (unit-cost estimate)
- Shadow Fast / Long: `648 / 1720`
- High-risk Shadow Fast: `0`
- Safety Shadow Fast: `0`
- Current route distribution: `{"governance_required": 880, "human_review_direct": 33, "low_touch": 1429, "not_applicable": 26}`
- Shadow reason distribution: `{"CLEAR_ORDINARY_REVIEW": 558, "EXISTING_SAFETY_GATE": 563, "FAST_ELIGIBILITY_NOT_PROVEN": 960, "GOVERNANCE_RISK_SIGNAL": 50, "HARD_LONG_TEXT_SIGNAL": 147, "STANDARD_LOW_COMPLEXITY_ISSUE": 90}`

## Observation Source

`{}`

## Gate

`STEP21_4_GATE = PASS`
Reason: `SAFETY_CLEAR_AND_REDUCTION_AT_LEAST_20_PERCENT`

## Isolation

- Production Router modified: `false`
- Short Chain executed by shadow: `false`
- Long Analysis executed by shadow: `false`
- Frozen benchmark executed: `false`
- Raw review text persisted: `false`

## Limitations

- The file sink targets the project's local single-process demo runtime; a multi-worker deployment would require a transactional metrics sink.
