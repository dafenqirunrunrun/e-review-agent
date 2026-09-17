# V1.6.6 Schema Consumer Alignment

Status: `CANONICAL_SCHEMA_SINGLE_SOURCE_PASS`
- consumer_count: `6`
- conflicting_consumer_count: `0`
| consumer | source | status |
| --- | --- | --- |
| `canonical_contract` | `app.contracts.e_review_decision` | `aligned` |
| `legacy_migration` | `app.contracts.e_review_decision` | `aligned` |
| `schema_failure_analysis` | `app.contracts.e_review_decision` | `aligned` |
| `prompt_renderer` | `app.contracts.e_review_decision` | `aligned` |
| `completion_only_encoder` | `app.prompts + app.contracts` | `aligned` |
| `task_evaluator` | `app.contracts.e_review_decision_migration` | `aligned` |
