# Step 20: Agent Runtime Reliability

## Gate

`STEP20_RUNTIME_GATE = PASS`

The review workflow now persists a bounded, atomic local checkpoint when explicitly enabled with `E_REVIEW_AGENTIC_CHECKPOINT_ENABLED=true`. The default remains disabled for compatibility with stateless callers. The local development environment enables it through the ignored `ai-service/.env` file.

## State Machine

`CREATED -> ROUTING -> RISK_ANALYSIS -> EVIDENCE_RETRIEVAL -> REFLECTION -> DECISION -> COMPLETED | WAIT_HUMAN`

`REFLECTION -> EVIDENCE_RETRIEVAL` is the only replan loop. Every active state can move to `FAILED`; terminal states reject further transitions. `WorkflowRuntime.transition` validates these edges before writing the checkpoint.

## Durable Boundary

Checkpoints are stored as atomic JSON files in `ai-service/data/workflow_checkpoints/` and are excluded from Git. A checkpoint contains the workflow/review ids, version, state, completed nodes, failure/retry metadata, bounded memory snapshot, final governance snapshot, and per-node input/output hashes with timing and error information.

The checkpoint deliberately excludes raw conversation history and full policy documents. It keeps only bounded workflow outputs, evidence references/snippets already returned by the policy layer, and structured memory required to explain a recovery.

## Recovery And Idempotency

After `evidence_1` is durably complete, a process crash leaves state `EVIDENCE_RETRIEVAL`. A new workflow instance detects that boundary and resumes at `REFLECTION`; it does not rerun intent routing, risk analysis, policy retrieval, embedding, or FAISS search. A terminal checkpoint returns the saved governance response for the same review id without invoking retrieval again.

Corrupted checkpoint JSON raises `WORKFLOW_CHECKPOINT_CORRUPT`; it is never silently replaced with a new automatic decision. Callers must route that review to human handling or explicitly repair the checkpoint.

Temporary node failures are recorded as retryable and are bounded to two retries. Validation/business failures are recorded as non-retryable. The node record is append-only within the checkpoint and includes start/end times, input/output hashes, status, retry count, and a bounded error message.

## Minimal Verification

Command:

```powershell
cd D:\EReviewAgent\litemall-v24-dataset-protocol\ai-service
.\.venv\Scripts\python.exe -m pytest tests\test_step20_runtime_checkpoint.py tests\test_step191_memory.py tests\test_step17_intent_safety.py tests\test_review_api.py tests\test_v25_agentic_policy_rag.py -q
```

Result: `40 passed, 4 warnings`.

Step 20-specific checks passed:

- Illegal `CREATED -> COMPLETED` transition is rejected.
- Node timing and input/output hashes survive a reload.
- Retryable and non-retryable failure classifications are persisted and bounded.
- A simulated crash after evidence resumes with reflection and does not call the retriever again.
- Repeating a completed review id returns the saved decision without another retrieval.
- Corrupted checkpoint input is detected rather than silently ignored.

## Operational Boundary

This is a single-host durable runtime implementation. Atomic file replacement protects a checkpoint write from partial content, but it is not a distributed lease or multi-host concurrency mechanism. Existing human-review database idempotency remains the authority for final human decisions. A future deployment with multiple AI-service replicas should replace this store behind the same runtime interface with the existing database or another shared transactional store.
