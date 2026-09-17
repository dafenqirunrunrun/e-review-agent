# V2.4 Agent Trace Contract

- Scope: AI Service synthetic qualification harness only; production runtime is not enabled.
- Schema version: `agent-trace.v1`.
- Event types: `21`; node types: `14`; status types: `9`.
- IDs use UUID4-style opaque values and are not derived from query, user, tenant, time, or database row IDs.
- Payload capture defaults to summary-only and raw query, prompt, evidence, model response, and tool arguments are excluded.
