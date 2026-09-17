# v1.8.0 Final Gate

Status: `V180_ENTERPRISE_READINESS_GATE_PASS_LOCAL`

## Main Results

- Full pytest: `299 passed in 197.76s`
- Maven admin-api build: `BUILD SUCCESS`
- External test isolation: `EXTERNAL_TEST_ISOLATION_AUDIT_PASS`
- Security hygiene: `SECURITY_HYGIENE_CHECK_PASS`
- Docker compose config: `PASS`
- Static CI workflow: `PRESENT`
- Real HTTP smoke: `V180_REAL_HTTP_SMOKE_PASS`
- 90-minute soak: `V180_90_MIN_SOAK_PASS`
- Failure injection: `V180_FAILURE_INJECTION_25_PASS`

## Enterprise RAG Evidence

- v1.7.0 truth audit downgraded old evidence to demo-only where appropriate.
- Local BGE-M3 embedding inventory and encode probe passed.
- Difficult multi-tenant RAG benchmark was generated without closed holdout, external test, or real user text.
- Real BGE-M3 + FAISS retrieval evaluation passed with persistent restart verification.
- Hash dense remains negative-control only, not primary enterprise evidence.

## Boundary

- No training was executed in v1.8.0.
- No adapter, model, or checkpoint was published.
- No release tag was created and no push was performed.
- Rebuildable FAISS binary index files are excluded from Git to satisfy model/index-binary hygiene.
- The CI workflow is a static readiness workflow; local model-dependent full pytest remains a local gate.
