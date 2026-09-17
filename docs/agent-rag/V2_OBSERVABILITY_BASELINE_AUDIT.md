# V2 Observability Baseline Audit

Phase: v2.0 Agent-RAG Enterprise Maturity - Observability and Runtime Resilience.

Baseline:

- Branch: `experiment/v2.0-agent-rag-governed-runtime`
- Expected starting HEAD: `d7d43b2f88025576f0c98d3ab7b70ce33bf31357`
- Tag at HEAD: none
- Scope: internal repository only
- Public snapshot repository: not touched

Pre-existing workspace boundary:

- The repository already contained historical audit refresh files and unrelated untracked files before this phase.
- This phase does not stage or modify those unrelated files.
- Generated `__pycache__` files were identified as cleanup candidates, but local command policy rejected direct deletion. They remain isolated as untracked cache artifacts and are not part of the phase commit.

Phase objective:

- Add operational observability around Agent-RAG without changing business semantics.
- Correlate Java and Python runtime requests by request id.
- Expose local metrics and health surfaces for demonstration and acceptance.
- Add single-node GPU concurrency guardrails and index hot-swap consistency protection.

Latest validation:

```text
pip check: PASS
python pytest: 471 passed, 11 skipped
real_dense marker: 1 passed, 7 skipped, 474 deselected
Java Agent-RAG targeted tests: 21 passed
mvn -DskipTests package: BUILD SUCCESS
Admin targeted lint: PASS
Admin unit test: 3 passed
Admin build: PASS with existing warnings
Observability E2E: AGENT_RAG_OBSERVABILITY_PASS
Local load: AGENT_RAG_LOCAL_LOAD_PASS
Local soak: AGENT_RAG_LOCAL_SOAK_PASS
Observability gate: AGENT_RAG_RUNTIME_RESILIENCE_PASS
```
