# Step 24.2A: RAG Quality Benchmark Foundation

## Status

```text
FOUNDATION_IMPLEMENTED
PROMOTION_READINESS_HOLD
HUMAN_ADJUDICATION_PENDING
PARSER_HARD_GATE_PASS
```

This plan is frozen before Step 24 bulk ingestion, parser-worker concurrency, or further retrieval tuning. Its purpose is to establish a trustworthy measurement contract before changing parser, chunking, retrieval, or reranking behavior.

## Why This Step Comes First

The project currently has several valid but different evaluation views:

- The frozen 120-case workflow set protects routing, safety, decisions, and regressions.
- The independent Chinese challenge set exposes generalization and ranking failures.
- The business evidence gate verifies whether useful policy support is available for governance.
- Citation checks verify traceability, not ranking quality.

These measurements must remain separate. A single Recall score must not be used to claim that the complete RAG system is good or bad. Historical oracle-style metadata and fixed query templates also mean that synthetic or familiar-query scores cannot be treated as real-world evidence.

## Evaluation Source Of Truth

The release source of truth will be:

```text
human-reviewed Chinese queries and graded qrels
  + deterministic information-retrieval metrics
  + policy-evidence business safety checks
```

Langfuse remains the experiment, trace, comparison, and online-sampling surface. RAGAS-style or claim-level model judges may be used only as non-blocking diagnostics until they have been calibrated against human judgments. Automatically generated questions may enter a candidate pool, but may not become gold without human review.

## Existing Dataset Responsibilities

### Frozen Workflow 120

- Keep content and SHA unchanged.
- Use for router, safety, workflow, reflection, decision, and API regression.
- Do not tune retrieval against it.

### Existing Chinese Challenge

- Keep as a versioned development and failure-analysis set.
- Repair qrels only through an explicit new dataset version.
- Never silently rewrite historical results.

### RAG Quality v2

Create one new retrieval-focused dataset with 120 Chinese queries:

- 80 development cases for diagnosis and bounded tuning.
- 40 untouched holdout cases for promotion decisions.
- A stable 24-case smoke subset selected from development cases for fast CI checks.
- Source documents may be Chinese or English, but every user query is Chinese.

Cases must cover explicit wording, semantic paraphrases, vague descriptions, multi-risk evidence, no-answer cases, near-neighbor clauses, tables, scanned PDFs, long sections, and policy-version ambiguity.

Each query uses graded chunk-level relevance:

```text
0 = irrelevant
1 = topically related but insufficient
2 = supporting evidence
3 = direct and preferred policy evidence
```

Each qrel also records supported risk types, source authority, clause identity, and whether the query intentionally has no answer.

## Judgment Method

Build a TREC-style candidate pool from the deduplicated Top-10 results of:

- BM25
- Qwen dense retrieval
- current hybrid retrieval
- B2 hybrid plus reranker candidate

Only pooled candidates require human judgment. Synthetic generation can draft difficult queries and candidate labels, but a human must approve the query intent and final qrels. High-risk and no-answer cases require a second independent review pass before freezing.

## Four Evaluation Layers

### 1. Document Parsing Gate

Measure parser output before chunking or embedding:

- parse success and explicit failure status by format
- page and content-anchor completeness
- heading hierarchy and clause-number retention
- list and reading-order preservation
- table row/cell preservation
- image/table/page association
- normalized AST traceability
- parser route and fallback observability
- no silent page, table, or asset loss

Use small representative fixtures for HTML, Markdown, TXT, CSV, XLSX, DOCX, PPTX, digital PDF, scanned PDF, and mixed table/image PDF. Borrow normalized text similarity, table structure, and reading-order concepts from document-parsing benchmarks without importing a large benchmark as a project dependency.

### 2. Retrieval And Ranking Gate

Measure candidate generation separately from reranking:

- Candidate Recall@5
- Candidate Recall@10 for diagnosis only
- MRR@5
- nDCG@3 and nDCG@5 using graded qrels
- risk evidence coverage at Top-3
- high-risk evidence hit at Top-5
- no-answer false-support rate
- duplicate and unjudged result rate
- citation validity
- per-slice results by risk type, query style, source language, and document format

Use a standard qrels/run calculation library such as `ir_measures`. All variant comparisons must retain per-query results, not only aggregate averages.

### 3. Workflow Business Gate

Verify the effect of retrieved evidence on governance:

- Reflection status accuracy
- evidence-supported rate
- partial-risk coverage behavior
- human-review recall
- high-risk automatic-pass count
- decision consistency
- no fabricated citation when evidence is absent
- BM25 fallback safety

### 4. Runtime And Capacity Gate

Measure operational cost without mixing it into quality scores:

- parser P50/P95 by format and page count
- chunking, embedding, FAISS, BM25, RRF, and reranker durations
- CPU, GPU, and memory peaks
- retries, failures, and fallback counts
- index build and atomic-publish duration
- batch success rate and queue throughput
- model, parser, chunker, index, and dataset version binding

The later 100-file concurrency test belongs to this layer, after the quality baseline is frozen.

## Evaluation Timing

```text
Before parser or chunker change
  -> freeze dataset, qrels, metric contract, and current baseline

After parser output
  -> run Document Parsing Gate

After chunk/index build
  -> run candidate Retrieval Gate

After reranker
  -> run paired Ranking A/B

After workflow integration
  -> run Business Gate

Before promotion
  -> run untouched holdout and repeated fresh-process regression

After deployment in shadow mode
  -> sample Langfuse traces and human-review disagreements
  -> add approved failures only to the next dataset version
```

## Precommitted Safety Gates

The following are hard requirements and may not be relaxed to promote a candidate:

```text
Citation Validity = 100%
High-risk Auto Pass Count = 0
High-risk Evidence Hit@5 = 100%
No fabricated citation for no-answer cases
No silent parser page/table loss
Frozen Workflow 120 SHA unchanged
```

Quality promotion thresholds for Recall, MRR, nDCG, coverage, and latency must be frozen after the first trustworthy baseline. They may not be chosen by looking at which threshold allows a preferred candidate to pass. A candidate must report overall and slice-level changes, and an aggregate improvement may not hide a safety-critical slice regression.

## Implementation Sequence

1. Freeze a single metric glossary and machine-readable evaluation contract.
2. Audit existing Chinese challenge qrels and record unresolved judgment gaps.
3. Build and release-review RAG Quality v2 with 80 development and 40 holdout cases.
4. Add deterministic qrels/run evaluation and per-query diagnostics.
5. Add parser fixture evaluation for structure, tables, reading order, and traceability.
6. Run current v1, D0, and B2 as factual baselines without tuning.
7. Freeze quality thresholds from the trustworthy baseline and business risk requirements.
8. Only then proceed to persistent parser workers, 100-file concurrency, chunking changes, or candidate promotion.

## Explicit Non-Goals

Step 24.2A must not:

- modify the frozen 120-case workflow gold
- tune RRF, embedding, reranker, router, or safety rules
- promote B2 to the online path
- treat unversioned, non-blind, unresolved LLM-judge scores as release truth
- add another observability platform beside Langfuse
- start the 100-file ingestion queue before the baseline is frozen
- combine parsing, retrieval, ranking, and governance into one opaque score

## Completion Definition

Step 24.2A is complete only when the metric contract, dataset versioning rules, graded qrels, parser fixtures, deterministic runner, current baselines, and promotion gates are executable and reproducible. Human gold remains the preferred external standard. For this personal-demo scope, a versioned LLM adjudication may authorize an internal frozen benchmark only when its machine provenance and limitations remain explicit.

## Implementation Checkpoint

Implemented artifacts:

- Machine-readable metric contract with explicit micro/macro aggregation semantics.
- 120-query Chinese candidate set: 80 development, 40 isolated Holdout, and 24 development smoke cases.
- Human annotation queue with mandatory second review for high-risk and no-answer cases.
- Deterministic qrels/run evaluator using `ir-measures==0.4.3`, per-case diagnostics, and multi-dimensional slices.
- Existing qrel audit, parser fixture evaluator, normalized v1/D0/B2 development baselines, and a read-only promotion-readiness gate.

The existing Chinese challenge remains diagnostic: 25 of 71 policy chunks are judged, 46 remain unjudged, and the judged-corpus coverage is `0.352113`. No historical qrel or frozen workflow case was rewritten.

Normalized existing-artifact results on the 80-case development split:

| Variant | Candidate Hit@5 | MRR@5 | Risk Coverage@3 | Citation Validity |
| --- | ---: | ---: | ---: | ---: |
| v1 | 1.0000 | 0.785897 | 0.753846 | 1.0000 |
| D0 | 1.0000 | 0.900000 | 0.892308 | 1.0000 |
| B2 | 1.0000 | 0.894103 | 0.907692 | 1.0000 |

These values are diagnostic only. They use partial candidate-exposed qrels and existing Top-5 artifacts; the source artifacts omit normal/no-answer retrieval runs, so abstention for those rows is an explicit placeholder rather than a measured result.

The initial parser fixture baseline passed 6 of 10 formats and exposed four losses. Step 24.2B repaired them without weakening the fixture contract:

- CSV table roots now carry a stable `sourceRef`.
- External parser workers run under an isolated ASCII user/cache/temp environment, avoiding the Docling Windows native-path failure.
- Docling and MinerU normalize the first visual heading as a title; MinerU content is ordered by page and bbox before hierarchy construction.
- Docling enables picture generation, with a `pypdf` object-level fallback that persists large embedded images and emits explicit figure-to-asset links.

The unchanged 10-format gate now passes `10/10` with `silentParserLossCount=0`. The frozen workflow SHA remains `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`.

## Step 24.2C Machine Adjudication Freeze

The user explicitly approved a machine-adjudicated personal-demo benchmark in place of human review. The resulting dataset is `rag-quality-v2-llm-frozen-1`; it must not be called human gold or an external benchmark.

- Codex performed the final semantic adjudication and completed every case against all 71 corpus chunks: 120 cases and 8,520 explicit relevance judgments.
- All 20 no-answer cases contain zero positive qrels, all 100 risk cases have supporting evidence for every expected risk type, and unresolved conflicts are zero.
- A local Qwen3-1.7B model ran two label-blind passes as an independent diagnostic. It completed 120 cases, but pairwise exact agreement was only `0.666667`, with 40 conflicts and 74 low-confidence cases. Its risk micro-F1 against the final adjudication was `0.680498` and `0.641975`, so it was rejected as a primary Judge.
- The 40-case Holdout is content-hash frozen and remains unexecuted. It was not consulted when setting thresholds.
- Quality thresholds were frozen from the B2 Dev baseline using `max(domain floor, Dev baseline - 0.05)` while exact safety gates remain unchanged.

Frozen thresholds:

| Metric | Threshold |
| --- | ---: |
| Candidate Evidence Hit@5 | 0.950000 |
| Relevant Chunk Recall@5 | 0.477869 |
| MRR@5 | 0.844103 |
| Pooled nDCG@5 | 0.556093 |
| Risk Coverage@3 | 0.857692 |
| High-risk Evidence Hit@5 | 1.000000 |
| Citation Validity | 1.000000 |
| No-answer Abstention Accuracy | 1.000000 |

The readiness result is `READY_WITH_SINGLE_JUDGE_LIMITATION`. This is sufficient for the project's personal-demo evaluation path, while the single-LLM and prior Dev exposure limitations remain permanently attached to the manifest. The next evaluation may execute Holdout exactly once; no threshold, qrel, parser, retrieval, or ranking change may be made after seeing that result without creating a new dataset version.

## Step 24.2D One-Shot Frozen Holdout

The frozen Holdout was consumed exactly once on 2026-09-12 UTC. The execution used only the precommitted B2 configuration: Qwen official-v2 query encoding, the frozen 71-vector FAISS index, equal-weight BM25/dense RRF with `k=60`, and local BGE reranking over Top-5. Retrieval was conditioned on the frozen upstream risk hints; cases with an empty frozen risk set abstained before retrieval, so this run does not re-evaluate Router quality.

The runner validated the frozen dataset, Holdout, qrels, metric contract, workflow gold, candidate index, embedding profile, reranker fingerprint, parser hard gate, and previous workflow safety gate before execution. Its independent seal prevents a second run. Result SHA-256: `733AFE785039EACA34DBE533EF6A6C581CB56B71E0D4F74330AD5F4682523CFE`.

```text
STEP24_2D_HOLDOUT_GATE = FAIL
```

| Metric | Observed | Frozen threshold | Result |
| --- | ---: | ---: | --- |
| Candidate Evidence Hit@5 | 1.000000 | 0.950000 | PASS |
| Relevant Chunk Recall@5 | 0.503030 | 0.477869 | PASS |
| MRR@5 | 0.743809 | 0.844103 | FAIL |
| Pooled nDCG@5 | 0.564085 | 0.556093 | PASS |
| Risk Coverage@3 | 0.742857 | 0.857692 | FAIL |
| High-risk Evidence Hit@5 | 1.000000 | 1.000000 | PASS |
| Citation Validity | 1.000000 | 1.000000 | PASS |
| No-answer Abstention Accuracy | 1.000000 | 1.000000 | PASS |
| Unjudged / duplicate rate | 0.000000 | 0.000000 | PASS |

The result is a ranking-generalization failure rather than a candidate-generation failure. All 35 risk cases had supporting evidence in Top-5, but relevant evidence was too often ranked below position one and multi-risk evidence was not fully covered in Top-3. The weakest slices were `long_noisy` privacy cases with MRR@5 `0.273333`, and `vague_risk_description` safety/after-sales cases with Risk Coverage@3 `0.000000`.

The B2 candidate is not promoted. This Holdout and its frozen thresholds must not be reused for tuning or rerun after a change. Any later repair must be developed against Dev and versioned challenge cases, then evaluated on a newly constructed untouched Holdout. The single-LLM Judge limitation remains in force, and the result must not be described as human-gold performance.
