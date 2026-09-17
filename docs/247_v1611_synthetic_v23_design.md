# V1.6.11 Synthetic SFT V2.3 Design

Status: `SYNTHETIC_V23_DESIGN_COMPLETE`

## Scope

- This stage designs v2.3 only.
- It does not generate formal v2.3 data.
- It does not train.
- It does not read or rerun the v2.2 holdout.
- Amazon/ASAP, external test, and real images are excluded.

## Target Composition

- total target: `720`
- train target: `576`
- validation target: `72`
- new engineering holdout target: `72`
- clear samples: `0.3`
- normal/negative boundary pairs: `0.2`
- negative/after-sales boundary pairs: `0.25`
- risk-level contrasts: `0.15`
- evidence-conflict human-review contrasts: `0.1`

## Holdout Rules

- new generation roots only: `true`
- exclude v2.2 holdout: `true`
- exclude v1.6.4 holdout: `true`
- sealed immediately: `true`
- single final evaluation: `true`
- risk type minimum per class: `24`
- risk level minimum per level: `18`

## Experiment Matrix

| Experiment | Single major factor changed | Fixed controls |
| --- | --- | --- |
| A | Synthetic v2.3 data | q/v modules, `r=8`, `epoch=1`, `max_length=384` |
| B | Epoch `1` to `2` | Only allowed if Experiment A proves underfit; early stopping required. |
| C | target modules `q/v` to `q/k/v/o` | Only allowed if A has sufficient data and token objective alignment but still no task gain. |

## Build Gate

`SYNTHETIC_SFT_V23_BUILD_ALLOWED`

Required gates: `V1610_RESULT_PERMANENTLY_FROZEN`, `VALIDATION_ONLY_DATA_ACCESS_GUARD_PASS`, `VALIDATION_FAILURE_ANALYSIS_COMPLETE`, `NO_GO_ROOT_CAUSE_CONFIRMED`, `SYNTHETIC_V23_DESIGN_COMPLETE`, `V22_HOLDOUT_EXCLUDED_FROM_V23`.
