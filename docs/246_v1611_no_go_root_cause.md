# V1.6.11 NO_GO Root Cause

Status: `NO_GO_ROOT_CAUSE_CONFIRMED`

This analysis keeps the v1.6.10 Adapter Value Gate unchanged: `NO_GO`. It does not read or rerun v2.2 holdout samples.

| Root cause | Confidence | Main evidence | Recommended intervention |
| --- | ---: | --- | --- |
| `ROOT_CAUSE_BASE_ALREADY_STRONG_ON_SCHEMA` | `0.72` | Base raw canonical schema valid rate is already `0.92592593`. | Do not spend the next iteration on schema-format learning. |
| `ROOT_CAUSE_TARGET_TEMPLATE_OVERFIT` | `0.74` | Normalized target duplicate rate is `0.61794872`; route reason top-5 share is `1.0`. | Increase target wording diversity while preserving canonical labels. |
| `ROOT_CAUSE_SYNTHETIC_SCENARIO_HOMOGENEITY` | `0.8` | Scenario family count is `9`; boundary sample count is `0`. | Generate explicit boundary and contrast quotas in v2.3. |
| `ROOT_CAUSE_SEMANTIC_LABEL_TOKEN_UNDERWEIGHT` | `0.62` | Semantic label token ratio is only `0.06600314`. | Rebalance examples so semantic labels are less template-correlated. |
| `ROOT_CAUSE_FORMAT_LEARNING_WITHOUT_TASK_GAIN` | `0.76` | Train loss reduction is `0.74392831`, but the value gate remains NO_GO. | Do not add epochs first; test data-first v2.3 Experiment A. |

Conclusion: the next valid experiment is data-first, not threshold tuning, holdout reruns, adapter override, or extra epochs as the first move.
