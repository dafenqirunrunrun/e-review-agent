# V2.3 Phase 9.0-9.1 Execution Status

## Repository

| Item | Value |
|---|---|
| Worktree | `litemall-v23-retrieval-recall-analysis` |
| Branch | `experiment/v2.3-retrieval-recall-analysis` |
| Starting HEAD | `e7378b5e` |
| Push | `NO_PUSH` |
| Tag | `NO_TAG` |
| Release | `NO_RELEASE` |

## Phase 9.0 Dataset

Dataset version: `v23-retrieval-qualification-v1`

Dataset hash: `d3835de362f936a3f5000395b57c447d1518e63a879e50a08e5198b920761c2d`

| Split | Answerable | No-answer |
|---|---:|---:|
| Calibration | 100 | 25 |
| Evaluation | 100 | 25 |
| Challenge | 40 | 10 |

Total cases: `300`

Answerable cases: `240`

No-answer cases: `60`

Gate: `E_REVIEW_V23_RETRIEVAL_DATASET_PASS`

Boundary:

- Full query text is not persisted in committed artifacts.
- Full chunk text is not persisted in committed artifacts.
- Case family and document family do not cross split.
- Dataset is aligned to the frozen tenant-a index snapshot used by the current real dense runtime.

## Current Retrieval Baseline

Baseline metrics hash: `bf7fc058647c30449b3dde46e4b3b7b61b1f9d807b1dd75df8212b3cf986d429`

| Metric | BM25 | Dense | RRF | Union Oracle |
|---|---:|---:|---:|---:|
| Recall@10 | 0.333333 | 0.279167 | 0.304167 | 0.320833 |
| Recall@20 | 0.608333 | 0.516667 | 0.525 | 0.579167 |
| Recall@50 | 0.779167 | 0.795833 | 0.745833 | 0.804167 |
| Recall@100 | 0.9 | 0.954167 | 0.891667 | 0.933333 |

Gate: `E_REVIEW_V23_RETRIEVAL_BASELINE_COMPLETE`

This is a frozen current baseline, not a quality improvement claim.

## Phase 9.1 Retrieval Miss Diagnostic Set

Diagnostic cases: `90`

Status: `CONSUMED_RETRIEVAL_MISS_DIAGNOSTIC_SET`

Future qualification allowed: `false`

| Metric | Value |
|---|---:|
| BM25 Top100 hits | 39 |
| Dense Top100 hits | 90 |
| Both Top100 hits | 39 |
| Neither Top100 hits | 0 |
| Union Top100 coverage | 1.0 |
| Candidate K recoverable | 90 |

Primary miss type:

```json
{
  "CANDIDATE_K_TOO_SMALL": 90
}
```

Candidate K recovery:

```json
{
  "CANDIDATE_K_10_RECOVERABLE": 38,
  "CANDIDATE_K_20_RECOVERABLE": 21,
  "CANDIDATE_K_50_RECOVERABLE": 26,
  "CANDIDATE_K_100_RECOVERABLE": 5
}
```

Gate: `E_REVIEW_V23_RETRIEVAL_MISS_ANALYSIS_COMPLETE`

## Optimization Priority

Recommended path: `PHASE_92_PRIORITY_CANDIDATE_K_AND_FUSION`

Why:

- All 90 old retrieval-missed answerable cases become recoverable within Top100.
- Dense Top100 alone sees all 90 cases.
- The current candidate pool size of 8 is the immediate bottleneck.
- Phase 9.2 should test Candidate K and fusion-window changes on calibration only, then evaluate on the unseen evaluation/challenge split.

## Resume Material

Problem:

The system had a major retrieval coverage bottleneck: only 74 of 164 answerable cases had relevant evidence in the current candidate pool, creating a 45.12% candidate coverage ceiling for downstream reranking and LLM answering.

Optimization / Engineering Action:

Built an unseen retrieval qualification benchmark with 300 synthetic, project-owned cases, enforced family-level split isolation, label validity audit, no-answer corpus audit, and old diagnostic leakage checks. Then froze the current BM25, BGE-M3 dense, RRF, and Union Oracle baseline without tuning runtime parameters.

Diagnostic Result:

For the old 90 retrieval-missed cases, Dense Top100 recovered 90/90 and Union Top100 coverage reached 100%, while all misses were classified as `CANDIDATE_K_TOO_SMALL`.

Engineering Decision:

Do not claim retrieval quality pass yet. Prioritize Phase 9.2 Candidate K and fusion-window experiments using the new calibration split, then validate on unseen evaluation/challenge splits.

## Test Results

| Command | Result |
|---|---|
| `python -m pip check` | PASS, no broken requirements |
| `python -m pytest -ra` | PASS, 505 passed, 16 skipped |
| `python -m pytest -ra -m real_dense` | PASS, 8 selected, 1 passed, 7 skipped |
| `python -m pytest -ra -m real_reranker` | PASS after fixture compatibility repair, 3 selected, 3 skipped because `FlagEmbedding` is unavailable |
| `python -m pytest -ra -m real_llm` | PASS, 1 selected, 1 passed |

Reranker note:

The `real_reranker` marker remains selected, but this environment does not provide `FlagEmbedding`, so the marked tests are skipped. This preserves the existing boundary that real reranker quality is not newly verified by Phase 9.0-9.1.

Resume-ready wording:

```text
Built a governed retrieval qualification framework for an enterprise RAG review-governance system, separating consumed diagnostic cases from unseen evaluation data. Diagnosed a 45.12% candidate coverage bottleneck and showed that 90/90 historical retrieval misses were recoverable within Dense/Union Top100, converting the problem from model failure into a measurable Candidate-K/fusion optimization roadmap.
```

## Existing Boundaries

Continue to preserve:

- `REAL_LLM_QUALITY_VERIFIED`
- `REAL_RERANKER_RUNTIME_VERIFIED`
- `REAL_RERANKER_EXPERIMENTAL_ONLY`
- `MODEL_RERANKER_NOT_VERIFIED`
- `AGENT_RAG_V22_REAL_MODEL_CHAIN_BLOCKED`
- `MODEL_FINE_TUNING_NOT_VERIFIED`
- `MILLION_SCALE_KNOWLEDGE_NOT_VERIFIED`
- `DISTRIBUTED_VECTOR_DATABASE_NOT_VERIFIED`
- `HIGH_AVAILABILITY_NOT_VERIFIED`
- `PRODUCTION_CONCURRENCY_NOT_VERIFIED`
- `ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED`
- `NO_PUBLIC_REPO_CHANGES`
- `NO_PUSH`
- `NO_TAG`
- `NO_RELEASE`
