# E-Review Agent Local Runbook

## Purpose

This runbook starts the local demo stack for the review governance workflow:

```text
wx-api 8082 -> AI service 8008 -> admin-api 8083 -> admin frontend 9527
```

The system must stay usable when AI, dense retrieval, Qwen, or FAISS is unavailable. In degraded mode, reviewers continue through manual review.

## Prerequisites

- Python 3.11 with `ai-service/.venv`
- Java 8 compatible JDK
- Maven
- Node.js and npm compatible with the existing `litemall-admin` package
- MySQL database `litemall`
- Optional local model weights outside Git:
  - `Qwen/Qwen3-Embedding-0.6B`
  - optional intent router model

## Configuration

Copy values from `.env.example` or `ai-service/.env.example` into the local shell or service manager.

Key safe defaults:

```text
E_REVIEW_AGENTIC_WORKFLOW_ENABLED=true
E_REVIEW_AGENTIC_MAX_ITERATIONS=2
E_REVIEW_AGENTIC_ROUTER_RULE_ENHANCEMENTS_ENABLED=true
E_REVIEW_HIGH_RISK_SAFETY_GATE_ENABLED=true
E_REVIEW_POLICY_RAG_ENABLED=true
E_REVIEW_POLICY_RAG_INDEX_PATH=data/policy_rag_real/index/policy_chunks.jsonl
E_REVIEW_POLICY_RAG_DENSE_RETRIEVAL_ENABLED=true
E_REVIEW_POLICY_RAG_BM25_FALLBACK_ENABLED=true
E_REVIEW_POLICY_RAG_TOP_K=3
E_REVIEW_POLICY_RAG_EMBEDDING_MODEL_PATH=
E_REVIEW_POLICY_RAG_EMBEDDING_ALLOW_REMOTE=false
E_REVIEW_POLICY_RAG_WARMUP_ENABLED=false
E_REVIEW_HUMAN_REVIEW_ENABLED=true
E_REVIEW_POLICY_EVIDENCE_DISPLAY_ENABLED=true
```

If the Qwen model path or FAISS index is invalid, readiness becomes degraded but BM25 fallback remains available when chunks exist.

## Build Policy Index

```powershell
cd <repo-root>\ai-service
.\.venv\Scripts\python.exe scripts\fetch_policy_sources.py
.\.venv\Scripts\python.exe scripts\build_policy_rag_index.py --input data\policy_rag_real\sources.json --output-dir data\policy_rag_real\index
.\.venv\Scripts\python.exe scripts\verify_real_policy_rag.py --chunks data\policy_rag_real\index\policy_chunks.jsonl --dense
```

Dense failure is acceptable for local demo if BM25 fallback passes.

## Start Services

For the complete local demo, use the managed launcher. It starts the AI runtime,
Admin API, Admin UI, document parser worker, and index worker, waits for HTTP
readiness, and records process ownership outside the repository. The Admin API
and both workers receive the same ephemeral worker token through their child
process environment; the token is never written to PID files or logs.

```powershell
cd <repo-root>
.\scripts\local\e-review-start.ps1 -NoMigration
.\scripts\local\e-review-status.ps1
```

Stop the complete managed process trees, including worker and interpreter child
processes, with:

```powershell
.\scripts\local\e-review-stop.ps1 -All
```

After a cold start, run the non-persisting Step 25 acceptance gate. It checks
normal-input abstention, policy evidence, the complete governance workflow,
read-only candidate comparison, and runtime index isolation.

```powershell
.\scripts\local\e-review-step25-acceptance.ps1
```

Its machine-readable result is stored under the local runtime directory at
`status/step25-acceptance.json`; credentials and review text are not stored in
that artifact.

The commands below remain useful when starting individual components manually.

AI service:

```powershell
cd <repo-root>\ai-service
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8008
```

Build the Java services once before starting them:

```powershell
cd <repo-root>
mvn -pl litemall-wx-api,litemall-admin-api -am -DskipTests package
```

Admin API:

```powershell
cd <repo-root>
java -jar litemall-admin-api\target\litemall-admin-api-0.1.0-exec.jar --server.port=8083
```

wx API:

```powershell
cd <repo-root>
java -jar litemall-wx-api\target\litemall-wx-api-0.1.0-exec.jar --server.port=8082
```

Admin frontend:

```powershell
cd <repo-root>\litemall-admin
npm run dev
```

## Health Checks

```powershell
Invoke-RestMethod http://127.0.0.1:8008/api/v1/health
Invoke-RestMethod http://127.0.0.1:8008/api/v1/system/liveness
Invoke-RestMethod http://127.0.0.1:8008/api/v1/system/readiness
Invoke-RestMethod http://127.0.0.1:8082/wx/home/index
Invoke-RestMethod http://127.0.0.1:8083/admin/auth/info -Headers @{"X-Litemall-Admin-Token"="<token>"}
```

Readiness does not expose local model paths. It reports model path as `configured`, `missing`, or `not_configured`.

## Minimal Smoke Test

Open:

```text
http://localhost:9527/#/goods/comment
http://localhost:9527/#/ai-workbench/governance-flow
```

Verify:

```text
评论列表 -> AI分析 -> 查看风险类型 -> 查看 Reflection -> 展开 Policy Evidence -> 打开原始政策 -> 人工复核 -> 最终状态
```

Reopening an existing `reviewId` should reuse the stored governance snapshot rather than recomputing embeddings.

## Audit And Migration

Apply the local schema migrations before starting the reviewer-facing runtime. Both commands are safe to repeat only when the migration itself uses `IF NOT EXISTS`; the rating-contract migration must be applied once per database and verified through the runtime gate.

```powershell
Get-Content -Raw litemall-db\sql\litemall_ai_governance_observation_v18.sql |
  mysql --default-character-set=utf8mb4 -h <host> -P <port> -u <user> <database>

Get-Content -Raw litemall-db\sql\litemall_comment_rating_contract_v21_4_2.sql |
  mysql --default-character-set=utf8mb4 -h <host> -P <port> -u <user> <database>
```

The first table is an observability dependency for the Admin analyze endpoint. The second removes the legacy `star=1` default and adds `rating_source`. Never infer `USER_PROVIDED` for legacy one-star rows because the old default and a real one-star rating cannot be distinguished.

Run the live rating-contract gate after services `8008`, `8082`, and `8083` are ready. Supply credentials only through process environment variables; the artifact never stores them.

```powershell
cd ai-service
.\.venv\Scripts\python.exe scripts\run_step2143_rating_runtime_gate.py
```

Audit recent tasks:

```powershell
cd <repo-root>\ai-service
.\.venv\Scripts\python.exe scripts\audit_review_governance_samples.py --limit 10
```

Historical compatibility dry-run:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_review_governance_history.py --dry-run --limit 200
```

Apply only after reviewing the dry-run report:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_review_governance_history.py --apply --limit 200
```

The migration is schema-only: it preserves the original snapshot in `originalGovernanceSnapshot`, never updates human task status or notes, and uses an optimistic database predicate so repeat runs are safe. Rows marked `requires_reevaluation` are historical semantic conflicts; they are not silently re-analysed.

Use a controlled fixture before applying to a development database:

```powershell
$env:PYTHONUTF8="1"
.\.venv\Scripts\python.exe scripts\migrate_review_governance_history.py --snapshot-json tests\fixtures\governance_history_rows.json --dry-run
```

## Explicit Historical Re-evaluation

Re-evaluation is intentionally separate from schema migration. It only selects snapshots whose `requiresReevaluation` field is `true`, runs the current v2 workflow, and appends `reevaluationHistory` rather than replacing the historical conclusion.

```powershell
cd <repo-root>\ai-service
$env:E_REVIEW_AGENTIC_WORKFLOW_ENABLED="true"
$env:E_REVIEW_POLICY_RAG_INDEX_PATH="data/policy_rag_real/index/policy_chunks.jsonl"
.\.venv\Scripts\python.exe scripts\reevaluate_review_governance_history.py --dry-run --limit 200
```

Use `--fixture tests\fixtures\governance_reevaluation_rows.json` for a repeatable development check. `--apply` is explicit and append-only: the analysis trace is updated with a new revision only when its original JSON still matches. It never changes risk-task status, handler, note, or operation logs.

## Latency Baseline

```powershell
cd <repo-root>\ai-service
.\.venv\Scripts\python.exe scripts\policy_rag_latency_baseline.py --samples 5
```

Record `avg`, `p50`, `p95`, and `max` for BM25, hybrid retrieval, cached reuse, and warm analyze.

## Step 16 Benchmark And Reliability Gate

The final controlled benchmark uses the real local 8008 service. Do not run it against a stale v1 process or a degraded dense provider.

```powershell
cd <repo-root>\ai-service
$env:E_REVIEW_AGENTIC_WORKFLOW_ENABLED="true"
$env:E_REVIEW_POLICY_RAG_EMBEDDING_MODEL_PATH="<your-local-model-path>"
$env:E_REVIEW_POLICY_RAG_EMBEDDING_ALLOW_REMOTE="false"
.\.venv\Scripts\python.exe scripts\run_step16_benchmark.py --write-dataset
.\.venv\Scripts\python.exe scripts\run_step16_benchmark.py --output artifacts\step16\benchmark_results.json
```

The runner executes BM25, dense, hybrid, and BM25 fallback retrieval; 120 real 8008 workflow requests; warm latency; 1/5/10/20 concurrency; cache checks; and non-destructive fault injection. Results are written to `ai-service/artifacts/step16/benchmark_results.json`; the human-readable analysis is `docs/BENCHMARK_REPORT.md`.

Before enabling any autonomous high-risk action, inspect `highRiskAutoPassFalseNegatives` in the result. The current fixed corpus has a release gate of zero. A non-zero result requires continued human review and a new benchmark run after an explicit routing-quality change.

The Step 17 safety gate is intentionally a routing guard, not a punishment decision: it moves implicit incentive, fake-review, review-suppression, privacy, or abuse language into the existing strict evidence workflow. Set either Step 17 flag to `false` only for controlled ablation; do not disable it in a reviewer-facing runtime.

## Common Failures

- AI service offline: frontend shows "AI 服务暂时不可用，可继续人工审核".
- Missing Qwen model path: readiness dense status is degraded; retrieval uses BM25 fallback.
- Missing FAISS index: readiness dense status is degraded; retrieval uses BM25 fallback.
- Missing policy chunks with strict index enabled: readiness degraded; workflow routes to human review.
- Duplicate human review: existing terminal status is returned and no second final decision is created.
- Frontend asset size warning: known build warning, not a runtime blocker.

## Controlled Fast Eligibility Runtime

The Step 21.5 runtime is disabled by default. It reuses the frozen Step 21.3H policy and never overrides the current Intent Router or Safety Gate. Eligible requests must already be `low_touch`, have no risk hints, have no image, and pass the frozen allowlist. Policy errors fail back to the existing baseline chain.

Use a bounded canary only after the readiness endpoint reports `policyIntegrity=ready`:

```properties
E_REVIEW_FAST_ELIGIBILITY_RUNTIME_ENABLED=true
E_REVIEW_FAST_ELIGIBILITY_RUNTIME_CANARY_PERCENT=10
E_REVIEW_FAST_ELIGIBILITY_RUNTIME_POLICY_PATH=artifacts/step213h_fast_eligibility_gate/fast_eligibility_policy_v1.json
```

Restart AI Service after changing these process settings. Roll back immediately by setting `E_REVIEW_FAST_ELIGIBILITY_RUNTIME_ENABLED=false` and restarting AI Service. Previously persisted results remain immutable; new requests return to the baseline chain.

Run the live Admin-to-AI verification with temporary credentials provided only through process environment variables:

```powershell
cd <repo-root>\ai-service
.\.venv\Scripts\python.exe scripts\run_step215_runtime_gate.py --latency-pairs 61
```

The gate creates isolated analysis fixtures, verifies Fast and baseline traces, checks zero high-risk/Safety Fast decisions, compares paired decisions and latency, then removes its database rows and checkpoints.

## Step 22 Final Acceptance

The final acceptance record is `docs/STEP22_FINAL_ACCEPTANCE_REPORT.md`. Its machine-readable companion is `ai-service/artifacts/step22/final_acceptance_gate.json`, while the full frozen benchmark output is `ai-service/artifacts/step22/frozen_benchmark.json`.

The accepted demo keeps Fast Eligibility disabled by default. High-risk actions remain human-confirmed, and dense retrieval failures retain the BM25 fallback path.

## Optional Langfuse v4 Sidecar

Langfuse is an observability and evaluation sidecar, never a governance dependency. Keep it disabled by default. To enable a self-hosted Langfuse v4 instance, set the following values in ignored `ai-service/.env` and restart 8008:

```properties
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_ENVIRONMENT=local
LANGFUSE_SAMPLE_RATE=1.0
```

The implementation uses the Python Langfuse SDK v4, which is OpenTelemetry-based and asynchronously exports traces. If the endpoint, keys, or SDK fail, review analysis continues normally. Never put credentials, raw review text, headers, tokens, or local model paths in telemetry configuration.

To build the sanitized local mirror of the frozen corpus before optional Langfuse dataset export:

```powershell
cd ai-service
.\.venv\Scripts\python.exe scripts\export_step16_langfuse.py --expected-gold-sha256 9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54
```
