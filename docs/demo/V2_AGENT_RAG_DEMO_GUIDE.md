# E-Review Agent v2.0 Agent-RAG Demo Guide

## Goal

Demonstrate the governed Agent-RAG review workflow with synthetic, non-PII data:

1. Runtime readiness.
2. Normal review analysis.
3. High-risk after-sales review.
4. Prompt-injection guard boundary.
5. Evidence and audit trail.
6. Human override and replay lineage through the Admin Operations Center.

## Prepare

```powershell
mvn -DskipTests package
powershell -ExecutionPolicy Bypass -File scripts\local\e-review-doctor.ps1 -Python D:\anaconda\envs\torchtest\python.exe
powershell -ExecutionPolicy Bypass -File scripts\database\e-review-migrate.ps1 -Apply
```

## Start

```powershell
powershell -ExecutionPolicy Bypass -File scripts\local\e-review-start.ps1 -Python D:\anaconda\envs\torchtest\python.exe -KeepExisting
```

## Seed Synthetic Demo Data

```powershell
powershell -ExecutionPolicy Bypass -File scripts\demo\e-review-demo-seed.ps1
```

Expected token:

```text
E_REVIEW_DEMO_SEED_PASS
```

## Demo Path

Open:

```text
http://127.0.0.1:9527/#/agent-rag/overview
```

Suggested explanation:

- "This overview shows the governed Agent-RAG runtime, not a plain chatbot."
- "The system stores bounded evidence, hashes, and workflow status for auditability."
- "High-risk reviews are routed to human operations instead of blindly accepting model output."
- "Prompt-injection requests are guarded and sent to manual review."
- "Real LLM quality and real model reranker quality remain explicitly unverified in this local RC."

Then open:

```text
http://127.0.0.1:9527/#/agent-rag/runs
```

Show:

- `demo-v2-normal-review`
- `demo-v2-high-risk`
- `demo-v2-prompt-injection`

## Cleanup

```powershell
powershell -ExecutionPolicy Bypass -File scripts\demo\e-review-demo-cleanup.ps1
```

Expected token:

```text
E_REVIEW_DEMO_CLEANUP_PASS
```

