# E-Review Agent Project Context

## Current State

The project provides an evidence-backed review-governance loop:

```text
Intent Router -> Planner -> Execution -> Policy Evidence RAG -> Reflection -> Replan or Human Review
```

The current policy RAG runtime is local and free: Qwen3-Embedding-0.6B through Transformers, FAISS, BM25 and RRF hybrid retrieval. A failure in dense retrieval must preserve BM25 fallback; evidence absence, invalid citations, or reflection mismatch must route to human review.

## Step 16 Baseline

The frozen controlled gold fixture is `ai-service/data/benchmarks/review_governance_gold_v1.jsonl` with 120 cases. The repeatable runner is `ai-service/scripts/run_step16_benchmark.py`, and the generated results live at `ai-service/artifacts/step16/benchmark_results.json`.

On the measured CPU-only local host, hybrid retrieval achieved Recall@1 0.9667 and Recall@5 0.9667 over 90 policy queries. Step 17 added bounded router semantic coverage plus a safety gate that routes uncertain high-risk language into strict evidence review. On the frozen 120-case corpus, real runtime risk-type F1 is now 0.7677 and expected-human-review auto-passes are 0. The system remains suitable for evidence-backed assisted review and human review; high-risk actions still require human confirmation.

See `docs/BENCHMARK_REPORT.md` for exact runtime, performance, fault-injection, and SLO evidence.

Step 18 adds production governance observations, QA sampling, bounded shadow audit, and benchmark configuration integrity guards. Three fresh complete runs verified actual Qwen/FAISS hybrid mode with Recall@1/@5 `0.9667 / 0.9667`, risk F1 `0.7677`, and zero high-risk auto-passes.

## Step 19.1 Memory

Step 19.1 adds per-review rolling governance memory only: structured risk/evidence/reflection/human-review state, iteration summaries, and a priority-aware context budget. It does not persist cross-review data and does not influence the current deterministic governance decision path. The final frozen benchmark after the 8008 service restart preserved Hybrid Recall@1/@5 `0.9667 / 0.9667`, Risk F1 `0.7677`, and zero high-risk auto-passes. See `docs/MEMORY_OPTIMIZATION_REPORT.md` and `docs/PERFORMANCE_REPORT.md` for measured context reduction and gate interpretation.

## Step 20: Agent Runtime Reliability

The Python agentic workflow has an optional durable local checkpoint runtime with an explicit legal state machine, per-node execution hashes, bounded retry classification, terminal-response idempotency, and recovery from the evidence checkpoint directly into reflection. The persisted payload is bounded workflow/governance state rather than conversational history or full policy text. See `docs/AGENT_RUNTIME_CHECKPOINT_REPORT.md` for the operational contract and passing minimal verification.

## Step 21.1: Langfuse Evaluation Sidecar

An optional Langfuse Python SDK v4 (OpenTelemetry-based) sidecar now emits a redacted agent trace, node span tree, runtime deterministic scores, and a sanitized frozen benchmark dataset mirror. It is disabled by default and fail-open. Live Langfuse UI verification remains pending a self-host endpoint and credentials; it is not a business source of truth.

## Step 21.5: Controlled Fast Path Activation

The frozen Step 21.3H Fast Eligibility policy is now available as a default-off runtime admission gate. Requests already classified as `low_touch`, with no risk hints and no image, may enter a deterministic Fast chain under a stable review-ID canary. High-risk, Safety Gate, low-rating governance, image, ambiguity, policy-integrity failure, and non-selected requests retain the existing baseline chain. Runtime decisions persist `executedChain`, reason code, policy version, and policy hash in the workflow trace.

The live Admin-to-AI gate passed all checks with zero high-risk Fast, zero Safety Fast, zero API errors, and zero paired decision mismatches. In the final gate artifact, median latency changed from `80.055 ms` to `69.774 ms`, a `12.8424%` reduction, while Fast P95 remained within the no-regression threshold. The feature remains disabled by default and can be rolled back with one environment switch. See `docs/FAST_ELIGIBILITY_RUNTIME_REPORT.md`.

## Step 22: Final Acceptance

The complete local business path is accepted for the personal free-local demo scope: real review input, agentic governance, hybrid policy retrieval, reflection, human review, idempotent resolution, audit persistence, and reviewer-facing citation display. The frozen 120-case benchmark preserved its SHA-256 and passed with Hybrid Recall@1/@5 `0.9667 / 0.9667`, Risk F1 `0.7677`, zero high-risk auto-passes, and zero API errors. Python, Java, frontend, build, database consistency, fallback, and browser checks passed. Fast Eligibility remains default-off and AI suggestions do not become autonomous punishment decisions. See `docs/STEP22_FINAL_ACCEPTANCE_REPORT.md`.

## Step 23: Truthful Agent Runtime Spans

Workflow observability now emits Langfuse spans around the actual execution intervals instead of reconstructing the normal workflow after completion. The runtime hierarchy distinguishes Router rules and Safety Gate, Risk Analysis, Planner, each Reflection iteration, EvidenceAgent, BM25, dense embedding, FAISS, RRF, Replan, checkpoint resume/persistence, and finalization. Low-touch requests do not emit policy-retrieval or reflection spans, and checkpoint recovery emits only the nodes that really resume.

The observer contract is fail-open and redacts review text, queries, credentials, local paths, and other sensitive input. Observability ON/OFF preserves the same governance result. The Step 23 focused and related workflow/API regression completed with `55 passed`; the dedicated runtime-span matrix completed with `7 passed`.

The post-acceptance roadmap is frozen as:

```text
Step 23 truthful Agent spans
-> Step 24 knowledge file library and ingestion jobs
-> Step 25 MinerU/Docling parser router and normalized Document AST
-> Step 26 structure-aware chunking v2 and precise citations
-> Step 27 bounded concurrent ingestion and atomic index publishing
-> Step 28 capacity/retrieval quality gate and vector-store decision
```

## Step 24.2A: RAG Quality Benchmark Foundation

Before continuing bulk ingestion or changing parser, chunking, retrieval, or reranking behavior, the project will establish a unified RAG quality benchmark. The approved design keeps the frozen 120-case workflow dataset unchanged, retains the existing Chinese challenge as versioned development evidence, and adds a new 120-query Chinese retrieval dataset with 80 development cases, 40 untouched holdout cases, and a stable 24-case smoke subset.

Evaluation is separated into document parsing, retrieval/ranking, workflow business safety, and runtime/capacity layers. Versioned graded qrels and deterministic IR metrics are the benchmark source of truth. Human gold remains preferred for external claims; the user has explicitly approved a machine-adjudicated internal benchmark for this personal demo, with the single-Judge limitation preserved in every frozen artifact. Langfuse remains the trace and experiment surface. Hard safety requirements include complete citations, zero high-risk auto-passes, complete high-risk evidence hit at Top-5, no fabricated no-answer citations, no silent parser page/table loss, and an unchanged frozen workflow SHA.

The metric contract, 80/40/24 Chinese candidate dataset split, annotation queue, qrel audit, deterministic retrieval evaluator, parser fixtures, normalized v1/D0/B2 development baselines, and read-only readiness gate are implemented. Focused and related regression completed with `47 passed`; the dedicated foundation suite completed with `7 passed`.

Step 24.2B repaired CSV graph traceability, the Docling Windows Unicode worker boundary, PDF title normalization, scanned-PDF reading order, and mixed-PDF image association. The unchanged parser gate now passes 10 of 10 fixtures with zero silent parser loss.

Step 24.2C froze `rag-quality-v2-llm-frozen-1` as an internal machine-adjudicated benchmark: 120 Chinese cases, an 80/40 Dev/Holdout split, and 8,520 complete judgments over the 71-chunk corpus. The local Qwen3-1.7B blind diagnostic was rejected as a primary Judge because its two-pass exact agreement was `0.666667`; Codex remains the single final semantic Judge, so the dataset is explicitly not human gold. Dev-only quality thresholds are frozen, parser safety remains `10/10`, and the frozen workflow SHA remains unchanged.

Step 24.2D consumed the frozen 40-case Holdout exactly once with the precommitted B2 protocol. The immutable execution seal records `STEP24_2D_HOLDOUT_GATE = FAIL`: Candidate Evidence Hit@5, Relevant Chunk Recall@5, pooled nDCG@5, citation validity, no-answer abstention, parser safety, and high-risk evidence safety passed, while MRR@5 was `0.743809` against `0.844103` and Risk Coverage@3 was `0.742857` against `0.857692`. The primary weaknesses are long noisy privacy queries and vague multi-risk safety/after-sales queries. B2 is not promoted, the consumed Holdout may not be rerun, and any remediation must use development data followed by a new untouched Holdout version. The complete plan, freeze, and one-shot result are recorded in `docs/STEP24_2A_RAG_QUALITY_BENCHMARK_PLAN.md` and `ai-service/artifacts/step242d/frozen_holdout_b2_result.json`.
