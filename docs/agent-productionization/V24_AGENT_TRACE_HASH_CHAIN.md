# V2.4 Agent Trace Hash Chain

- Each event stores previousEventHash and eventHash over canonical JSON.
- The chain is tamper-evident, not a digital signature and not a substitute for KMS or WORM storage.
- Modify, delete, insert, and reorder tamper cases are detected by the integrity verifier.
