# V1.6.2 Private Noncommercial Research Mode

Status: `PRIVATE_NONCOMMERCIAL_RESEARCH_MODE_ACTIVE`

This branch separates formal authorization gates from local, private, noncommercial engineering research gates.

Allowed local activities:

- Local code development
- Local model inference
- Private exploratory text evaluation
- Private RAG compatibility experiments
- Project-owned synthetic training workflow validation
- Existing public pilot local read-only compatibility checks

Still blocked:

- Formal external evaluation
- Public result release
- Restricted real/public pilot training
- Public pilot SFT, DPO, or VLM training
- Model weight redistribution
- Current real pilot images entering VLM

`V161_FINAL_GATE_BLOCKED` is retained with a narrowed meaning: it blocks formal use, formal benchmark claims, release, redistribution, and restricted-data training. It does not block local private engineering experiments that pass the v1.6.2 private research gate.
