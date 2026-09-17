# V1.6.5 Schema Contract Matrix

Status: `SCHEMA_CONTRACT_MISMATCH_CONFIRMED`
- mismatch_count: `9`

| field | training | evaluation | API/runtime | repair_output |
| --- | --- | --- | --- | --- |
| `risk_type` | `False` | `True` | `True` | `True` |
| `risk_level` | `False` | `True` | `True` | `True` |
| `text_evidence` | `False` | `True` | `False` | `True` |
| `visual_evidence` | `False` | `False` | `False` | `False` |
| `retrieved_case_evidence` | `False` | `True` | `False` | `True` |
| `need_human_review` | `False` | `True` | `True` | `True` |
| `route_reason` | `False` | `True` | `False` | `True` |
| `missing_information` | `False` | `True` | `True` | `True` |
| `unsupported_claims` | `False` | `True` | `False` | `True` |
