# V1.6.11 Validation Failure Analysis

Status: `VALIDATION_FAILURE_ANALYSIS_COMPLETE`

## Data Access Scope

- v2.2 holdout raw text read: `false`
- v2.2 holdout reinference: `false`
- analysis inputs: train metadata, validation split, aggregate v1.6.10 reports, and Git-external validation predictions only.
- prediction source: `VALIDATION_PREDICTIONS_REUSED_OFFLINE`
- initial prediction status in this stage: `VALIDATION_PREDICTIONS_REQUIRED_ONCE`
- one-time validation inference executed: `true`
- prediction rows: `108` (`base=54`, `adapter=54`)

## Validation Metrics

| Model | Coverage | Fallback | Coverage-adjusted accuracy | Risk type macro-F1 | Risk level macro-F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Base Qwen3-1.7B | `0.92592593` | `0.07407407` | `0.35185185` | `0.70909091` | `0.36948854` |
| Base + v2.2 Adapter | `0.74074074` | `0.25925926` | `0.51851852` | `0.73596593` | `0.66067019` |

The adapter improves validation semantic accuracy among covered predictions, but it loses coverage and increases fallback/abstention. This supports retaining the v1.6.10 holdout NO_GO conclusion rather than overriding it with validation-only evidence.

## Training Curve

- initial train loss: `1.5460374057292938`
- final train loss: `0.3958964180201292`
- relative train loss reduction: `0.74392831`
- final validation loss: `0.4064420169150388`
- train/validation gap: `0.0105456`
- judgement: `OPTIMIZATION_STABLE_SIGNAL_WEAK`

The loss curve shows optimization progress, but the validation and holdout evidence do not justify more epochs as the first next step.

## Distribution And Slices

- adapter class distribution: `DISTRIBUTION_NON_COLLAPSED`
- adapter dominant class rate: `0.65`
- adapter prediction distribution: `normal_review=26`, `negative_review=9`, `after_sales_risk=5`
- weakest semantic slice: `after_sales_risk`, adapter risk accuracy `0.3125`
- largest coverage regression slice: `negative_review`, base coverage `1.0`, adapter coverage `0.5`

## Template And Diversity

- normalized target duplicate rate: `0.61794872`
- route reason top-1 share: `0.41794872`
- template signal: `TARGET_TEMPLATE_OVERFIT_RISK`
- scenario family count: `9`
- boundary sample count: `0`
- scenario diversity status: `SCENARIO_DIVERSITY_WEAK`

## Token Objective

- status: `SFT_TOKEN_OBJECTIVE_ALIGNMENT_WEAK`
- completion token count: `3818`
- structural token ratio: `0.77789419`
- semantic label token ratio: `0.06600314`
- evidence token ratio: `0.0547407`
- explanation token ratio: `0.10136197`
