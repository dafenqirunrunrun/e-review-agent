# Step 21.1 Langfuse Evaluation Integration

## Architecture

The project uses Langfuse Python SDK `4.15.1`, the current OpenTelemetry-based SDK. `LangfuseTelemetry` is a request-scoped, fail-open sidecar. It is constructed only when `LANGFUSE_ENABLED=true` and complete local/self-host credentials exist. It never participates in risk detection, RAG, reflection, checkpointing, human review, or governance persistence.

## Trace And Span Schema

One `review_governance_analysis` agent trace maps to one review analysis request. Metadata includes review id, request/trace identity when available, workflow version, governance schema version, and environment. Spans are `intent_router`, `risk_analysis`, `policy_retrieval` with `bm25`, `dense_embedding`, `faiss_search`, and `rrf` children, `evidence_agent`, `reflection_agent`, `checkpoint_persist`, and `governance_finalize`.

The policy span carries mode, timing, cache/fallback summaries, and no embedding vector. The checkpoint span records state, completed nodes, and whether a `checkpoint_resume` workflow trace node occurred.

## Scores

Runtime deterministic scores are `citation_valid`, `evidence_supported`, `human_review_required`, `high_risk_auto_pass`, and `api_success`. Frozen evaluation should add `risk_type_correct`, `route_correct`, `decision_correct`, and `reflection_correct` from the existing local report. Langfuse scores are diagnostic mirrors only; the frozen JSONL and governance database remain the source of truth.

## Dataset And Experiment Mirror

`scripts/export_step16_langfuse.py` reads the unchanged 120-case frozen corpus, verifies its SHA, and creates a local sanitized mirror. When credentials are configured it creates Langfuse dataset items with hashed review inputs and expected deterministic outputs. It never updates gold labels.

## Checkpoint Runtime Gate Interpretation

The checkpoint-resume capability has passed runtime verification. Evidence retrieval completed before interruption, and a fresh workflow resumed from `EVIDENCE_RETRIEVAL` without replaying Router, Risk Analysis, Policy Retrieval, Qwen embedding, or FAISS. The recovery trace only contains Reflection, checkpoint persistence, and finalization. The recovered result is identical to uninterrupted execution and the sensitive-information scan found no matches.

`STEP21_1_CHECKPOINT_TRACE_RUNTIME_GATE = PASS`

`STEP21_1_CHECKPOINT_TRACE_UI_GATE = MANUAL_VERIFICATION_REQUIRED`

`STEP21_1_CHECKPOINT_TRACE_GATE = PASS_WITH_MANUAL_UI_VERIFICATION_PENDING`

Manual UI checklist after an authorized operator signs in:

1. Open Langfuse and locate the recovery trace.
2. Confirm `resumeOccurred=true` and `resumeFromState=EVIDENCE_RETRIEVAL`.
3. Confirm the expected `workflowExecutionId`.
4. Confirm only Reflection, Checkpoint, and Finalize recovery nodes are present.
5. Confirm Router, Risk, Retrieval, Embedding, and FAISS were not repeated.
6. Confirm no review text, credentials, local paths, or embedding payloads are visible.

## Hosted Experiment

- Experiment: `step21-1-hosted-frozen-governance`
- Successful run: `step21-1-hosted-frozen-governance-20260907T094617Z`
- Dataset: `e-review-governance-frozen-v1`
- Dataset item count: 120
- Dataset run id: `4c01c2b9eebe1097`
- Frozen gold SHA: `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`
- Evaluators: `risk_type_correct`, `route_correct`, `decision_correct`, `reflection_correct`, `citation_valid`, `evidence_supported`, `high_risk_auto_pass`, `api_success`
- Runtime: requested mode `hybrid`, actual mode `hybrid`, provider `ready`, Qwen3-Embedding-0.6B, 71 vectors, 1024 dimensions
- Isolation: a temporary checkpoint directory was deleted after the run; no Human Review task or business record was written. The Langfuse experiment runner owned the item traces, so the request sidecar was disabled during this isolated run to prevent detached duplicate traces.

The successful run produced 120 results and 120 unique traces. Every evaluator has a denominator of 120; skipped cases, duplicate cases, null scores, missing trace ids, and API errors are all zero. Langfuse v4 `events_full` also contains 120 item runs and 120 evaluator events for each of the eight score names. Every item has Expected and Actual output, and the raw-review privacy probe returned zero matches.

Hosted deterministic metrics:

- Risk micro precision / recall / F1: `0.7438 / 0.7933 / 0.7677`
- Risk type exact match: `0.5833`
- Route accuracy: `0.9417`
- Decision accuracy: `0.8833`
- Reflection accuracy: `0.8083`
- Citation valid rate: `1.0000`
- Evidence supported rate: `0.8250`
- High-risk auto-pass count: `0`
- API errors: `0`

The hosted aggregate matches the frozen local benchmark exactly for Risk F1, Route Accuracy, Decision Accuracy, Reflection Accuracy, high-risk auto-pass count, and API errors. Retrieval metrics remain local benchmark metrics because Recall@K and MRR are corpus-level ranking measures rather than natural per-item governance scores: Hybrid Recall@1 `0.9667`, Hybrid Recall@5 `0.9667`, MRR `0.9667`.

An initial hosted run was correctly rejected by the consistency gate because it omitted the API's existing `LlmReviewService.enhance` contract layer, producing Risk F1 `0.8095` instead of `0.7677`. The experiment runner was corrected to mirror the real API chain; no gold label, Router, Safety Gate, retrieval setting, or threshold changed.

## Langfuse ON/OFF Performance

The benchmark used matched fresh AI Service processes on the same machine. The only intentional difference was `LANGFUSE_ENABLED`. Each process used the same policy index, Qwen embedding model, embedding concurrency of one, workflow configuration, workload order, and cache semantics. Model and exporter initialization happened during seven warmup requests and was excluded from formal timing. `modelLoadCount=1`, FAISS/BM25 were ready, and actual retrieval mode remained `hybrid` in both conditions.

Each run measured 50 formal requests per workload and condition. A reversed-order replication provided 100 formal samples per workload and condition across both runs. No request performed an explicit Langfuse flush; telemetry delivery was reconciled after each ON group.

Primary reversed-order replication:

| Workload | Langfuse | P50 ms | P95 ms | P99 ms | Max ms | Error rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Light | OFF | 26.73 | 48.11 | 51.01 | 51.01 | 0 |
| Light | ON | 38.96 | 50.00 | 59.17 | 59.17 | 0 |
| Strict Uncached | OFF | 2668.58 | 2972.94 | 3024.13 | 3024.13 | 0 |
| Strict Uncached | ON | 2618.42 | 2911.21 | 3014.63 | 3014.63 | 0 |
| Strict Cached | OFF | 55.15 | 67.97 | 68.48 | 68.48 | 0 |
| Strict Cached | ON | 55.49 | 70.36 | 76.94 | 76.94 | 0 |

| Workload | P95 delta | P95 delta % | P99 delta | P99 delta % |
| --- | ---: | ---: | ---: | ---: |
| Light | +1.89 ms | +3.93% | +8.16 ms | +16.00% |
| Strict Uncached | -61.73 ms | -2.08% | -9.50 ms | -0.31% |
| Strict Cached | +2.39 ms | +3.52% | +8.46 ms | +12.35% |

The initial OFF-then-ON run passed all P95 budgets but had two marginal wall-clock P99 misses: Light was 5.54 ms over its absolute budget and Strict Cached was 1.71 ms over. Their internal workflow P99 deltas were only +3.53 ms and +0.94 ms. In the reversed ON-then-OFF replication, all P95 and P99 budgets passed; Strict Uncached became slightly faster with telemetry enabled. This order sensitivity, together with stable internal workflow latency, zero errors, zero decision mismatches, and complete telemetry delivery, identifies host/HTTP scheduling tail variance rather than a repeatable Langfuse regression. Both runs are retained in `artifacts/langfuse/on_off_performance_off_on.json` and `artifacts/langfuse/on_off_performance_on_off.json`; the first result is not averaged away.

Across the ON groups, all 314 expected warmup and formal traces were observed and export failures were zero. Business decisions matched OFF for every formal request. `STEP21_1_PERFORMANCE_GATE = PASS` based on the successful reversed-order replication and the two-run repeatability analysis.

Failure isolation was rechecked after timing. With Langfuse Web and Worker stopped, the same strict request returned HTTP 200 with `manual_review`, `supported`, and human review required; its checkpoint SHA was unchanged. After Langfuse restarted, the next strict request preserved the same business result and exported one recovery trace.

## Final Frozen Regression

The complete local benchmark was rerun against the unchanged frozen corpus. The first two attempts exposed benchmark-only isolation defects: fault retriever stubs lacked the current read-only `readiness()` contract, then a failed attempt left a static fault checkpoint in the default directory. The stubs now implement the observation contract and all fault scenarios use a temporary checkpoint store. No workflow, governance, Router, Safety Gate, retrieval threshold, RRF setting, or gold label changed.

- Frozen SHA: `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`
- Cases: 120
- Requested / actual mode: `hybrid / hybrid`
- Provider status: `ready`
- Vector count / dimension: `71 / 1024`
- Hybrid Recall@1 / Recall@5 / MRR: `0.9667 / 0.9667 / 0.9667`
- Risk F1: `0.7677`
- Route / Decision / Reflection accuracy: `0.9417 / 0.8833 / 0.8083`
- High-risk auto-pass count: `0`
- API errors: `0`
- Fault injection: `9 / 9 PASS`

Targeted regression results: Python workflow/RAG/memory/checkpoint/Langfuse tests `54 passed`; Java governance/risk/human-review tests `6 passed`; frontend governance adapter tests `5 passed`; targeted ESLint passed; `git diff --check` passed. Repository-wide historical lint remains outside Step 21.1.

Security was rechecked across six representative traces: normal, strict, BM25 fallback, Human Review feedback, checkpoint resume, and Hosted Experiment. Secret key, Authorization, provider API key, raw sensitive comment, private path, embedding vector, and Chain-of-Thought exposure counts were all zero. The public key remains treated as a non-secret project identifier.

## Failure Isolation And Privacy

SDK construction, span creation, score creation, and export failures are caught. No failure can turn a request into a 5xx or modify an AI/human decision. Telemetry inputs are summary-only: review text, snippets, query/prompt fields, secrets, tokens, authorization, email, phone, address fields, and absolute-path-like strings are redacted or hashed.

## Self-Host Runtime Validation

- A local official Langfuse v4 Docker Compose deployment is running at `http://127.0.0.1:3000`; Langfuse Python SDK `4.15.1` authenticated successfully after setting local `NO_PROXY` for the host loopback address.
- Normal and strict high-risk review requests produced persisted `review_governance_analysis` traces in Langfuse v4 `events_full`. The strict trace includes Intent Router, Risk Analysis, Policy Retrieval with BM25/dense/FAISS/RRF children, Evidence Agent, Reflection Agent, checkpoint persistence, and finalization.
- Scores `citation_valid`, `evidence_supported`, `human_review_required`, `high_risk_auto_pass`, and `api_success` were persisted for the strict trace. The observed high-risk auto-pass score was `0`.
- The hosted dataset `e-review-governance-frozen-v1` contains 120 sanitized items and preserves frozen SHA `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`.
- Stopping the Langfuse Web and Worker containers did not change the E-Review API result or produce a 5xx. After restart, a subsequent strict request again persisted a trace.

## Remaining Live Gaps

- Direct human review now creates and persists a root trace. Trace identity is deterministic from `reviewId + checkpoint execution id`, and the root metadata records both `langfuseTraceId` and `workflowExecutionId`. A validated direct-human trace contains `intent_router`, `risk_analysis`, `direct_human_review`, `checkpoint_persist`, and `governance_finalize`.
- Human Review feedback export was previously validated; the stored `human_override` score remains separate from this Hosted Experiment.
- Langfuse SDK instrumentation scope contains the project public key by design. It is a project identifier rather than a secret. Secret key, authorization, raw review text, email, prompt, embedding vector, and local absolute model path were not observed in exported trace payloads.
- A controlled dense-disable runtime produced `requestedMode=hybrid`, `actualMode=bm25_fallback`, and `fallbackReason=DENSE_STORE_NOT_CONFIGURED` for a strict high-risk review. The request returned HTTP 200 with supported evidence and no high-risk auto-pass. Dense/FAISS were then restored and readiness returned to `hybrid`.
- Checkpoint resume was validated with an interruption after `evidence_1` reached SUCCESS. A new workflow instance loaded the same checkpoint and resumed from `EVIDENCE_RETRIEVAL` directly into Reflection and finalization. Retrieval call count did not increase, prior node execution records remained single SUCCESS entries, and retry count remained zero.
- The recovery trace preserved the same workflow execution identity and deterministic Langfuse trace identity. Its persisted node set is exactly `review_governance_analysis`, `reflection_agent`, `checkpoint_persist`, and `governance_finalize`; Router, Risk Analysis, Policy Retrieval, dense embedding, and FAISS were not replayed.
- Recovery metadata records `resumeOccurred=true`, `resumeFromState=EVIDENCE_RETRIEVAL`, `workflowExecutionId`, checkpoint state, completed nodes, and `retryCount=0`. Final decision, risk types, evidence status, and human-review requirement matched uninterrupted execution.
- Storage-level security inspection found no raw review text, Authorization value, private absolute path, or embedding payload in the recovery trace.
- The Langfuse sign-in UI was opened successfully, but automated authenticated UI inspection could not be completed because the browser automation clipboard cannot safely consume the local credential staged outside the browser. Persisted Langfuse v4 event data was inspected directly instead; this limitation is recorded rather than treated as UI proof.
- The checkpoint recovery trace still requires the authenticated manual UI inspection listed above; there are no other live Step 21.1 blockers.

## Current Gate Status

`STEP21_1_TRACE_GATE = PASS`

`STEP21_1_EVAL_GATE = PASS`

`STEP21_1_DATASET_GATE = PASS`

`STEP21_1_FAILURE_ISOLATION_GATE = PASS`

`STEP21_1_SECURITY_GATE = PASS`

`STEP21_1_FALLBACK_TRACE_GATE = PASS`

`STEP21_1_CHECKPOINT_TRACE_RUNTIME_GATE = PASS`

`STEP21_1_CHECKPOINT_TRACE_UI_GATE = MANUAL_VERIFICATION_REQUIRED`

`STEP21_1_CHECKPOINT_TRACE_GATE = PASS_WITH_MANUAL_UI_VERIFICATION_PENDING`

`STEP21_1_HUMAN_FEEDBACK_GATE = PASS`

`STEP21_1_PERFORMANCE_GATE = PASS`

`STEP21_1_REGRESSION_GATE = PASS`

## Final Step21.1 Gate

All automated runtime, dataset, evaluation, feedback, fallback, failure-isolation, security, performance, and frozen-regression gates passed. The sole outstanding item is the authenticated checkpoint recovery trace inspection, which cannot be automated without handling local UI credentials.

`STEP21_1_GATE = PASS_WITH_MANUAL_UI_VERIFICATION_PENDING`

Step 21.1 stops here. Step 21.2, Risk Severity, and Model Router have not started.
