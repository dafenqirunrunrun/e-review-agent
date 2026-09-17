# v2.1 Knowledge Scale Qualification

## Scope

This module validates deterministic synthetic knowledge scale behavior for the
v2.1 qualification branch. It does not use customer data and does not commit the
generated raw knowledge files or index material.

## Generator

Added:

```text
ai-service/scripts/qualification/generate_scale_knowledge.py
```

Properties:

- Deterministic seed.
- Multi-tenant records.
- Public and tenant-scoped knowledge.
- Active, inactive, effective, and expired records.
- Duplicate and near-duplicate groups.
- Chinese and English synthetic text.
- Synthetic-only data.

Generated raw files were written to an external qualification artifact
directory. Only the compact summary is tracked in Git.

## Qualification Runner

Added:

```text
ai-service/scripts/qualification/run_scale_qualification.py
```

The runner performs:

- Synthetic generation.
- Local lexical index construction.
- Fixed query evaluation.
- Tenant isolation checks.
- Inactive and expired leakage checks.
- Duplicate evidence checks.
- Query latency measurement.

## Results

| Scale | Status | nDCG@5 | MRR | Recall@5 | Query P95 ms | Tenant violations | Expired leakage |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1K | PASS | 1.000000 | 1.000000 | 1.000000 | 1.2695 | 0 | 0 |
| 10K | PASS | 1.000000 | 1.000000 | 1.000000 | 8.1747 | 0 | 0 |
| 100K | PASS | 1.000000 | 1.000000 | 1.000000 | 83.0826 | 0 | 0 |

Summary artifact:

```text
artifacts/qualification/scale-qualification-summary.json
```

## Tokens

```text
AGENT_RAG_SCALE_1K_PASS
AGENT_RAG_SCALE_10K_PASS
AGENT_RAG_SCALE_100K_PASS
MILLION_SCALE_KNOWLEDGE_NOT_VERIFIED
```

## Boundary

The 100K result is a local deterministic synthetic qualification result. It is
not a production capacity claim and it is not evidence for distributed vector
database behavior.
