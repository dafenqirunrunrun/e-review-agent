# V2.4 Agent Trace Security And Redaction

- Sensitive fields are denylisted and summarized with HMAC-SHA-256.
- Raw query/prompt/evidence/tool argument leak counts are all `0` in the synthetic qualification artifact.
- Payload capture is disabled by default; only counts, hashes, schema hashes, state transitions, and safe summaries are stored.
