# v2.1 Multi-Process Index Consistency Qualification

## Scope

This module validates a shared activation-manifest pattern with independent
Python worker processes. It does not share mutable in-memory FAISS objects across
processes.

## Mechanism

The qualification script uses:

- Shared active generation manifest.
- Generation number.
- Provider fingerprint.
- Index checksum.
- File lock.
- Atomic manifest replacement.
- Independent per-process in-memory index handles.

Script:

```text
ai-service/scripts/qualification/run_multi_process_index_consistency.py
```

## Scenario

Executed with two independent worker processes:

1. Activate `generation-a`.
2. Confirm both workers load `generation-a`.
3. Activate `generation-b`.
4. Confirm both workers load `generation-b`.
5. Activate a corrupt `generation-a` manifest with an invalid checksum.
6. Confirm both workers reject the corrupt manifest and keep `generation-b`.
7. Restore valid `generation-a`.
8. Confirm both workers roll back to `generation-a`.

## Result

Summary artifact:

```text
artifacts/qualification/multi-process-index-summary.json
```

Observed:

- Worker count: 2
- Mixed generation response: 0
- Closed-index errors: 0
- Tenant violations: 0
- Checksum reject verified: true
- Rollback verified: true

Token:

```text
AGENT_RAG_MULTI_PROCESS_INDEX_CONSISTENCY_PASS
```

## Boundary

This is a local multi-process consistency qualification. It is not a distributed
vector database claim and it does not remove high-availability or production
concurrency boundaries.
