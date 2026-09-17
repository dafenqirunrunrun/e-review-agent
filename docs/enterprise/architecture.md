# Enterprise Architecture

```mermaid
flowchart LR
  Client["Client or Java backend"] --> API["Enterprise FastAPI /api/v1/e-review"]
  API --> Guard["Input guard and PII redaction"]
  Guard --> Agent["Governed Agent"]
  Agent --> RAG["Hybrid RAG"]
  RAG --> Verify["Evidence verifier"]
  Agent --> Provider["TextProviderFactory"]
  Provider --> Base["Base provider"]
  Provider -.feature flag.-> Adapter["Private adapter provider"]
  Provider -.sample.-> Shadow["Non-blocking shadow"]
  Agent --> Human["Human review router"]
  API --> Audit["Safe audit and metrics"]
```

Default runtime mode is `base`. Adapter mode is feature-flagged and rolls back to Base on validation or runtime failures. Shadow execution is non-blocking and stores only aggregate agreement metrics.
