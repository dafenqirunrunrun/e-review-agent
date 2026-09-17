# Step 19 Performance Report

## Baseline

This report was measured on 2026-09-07 on the local CPU-only Qwen runtime, using the frozen 71-chunk policy index and `Qwen/Qwen3-Embedding-0.6B` (1024 dimensions). The frozen 120-case gold SHA is `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`.

Step 16's warm strict path P95 was 1,013.34 ms. Step 19 does not change the Router, Safety Gate, gold data, policy sources, RRF parameters, or final-decision semantics.

## Latency Breakdown

| Path | Samples | Total P50 | Total P95 | Primary measured cost |
| --- | ---: | ---: | ---: | --- |
| Cold strict | 1 | 10,794.52 ms | 10,794.52 ms | Local model load plus embedding |
| Warm strict, no query cache | 8 | 1,163.01 ms | 1,172.71 ms | Qwen embedding compute |
| Warm strict, cache hit | 8 | 30.37 ms | 36.56 ms | BM25 and workflow overhead |

For warm uncached strict requests, median embedding compute was 1,132 ms. BM25 was 12.06 ms, FAISS and RRF were sub-millisecond, Reflection was below 0.1 ms, and routing/risk detection stayed below 10 ms. The measured bottleneck is therefore Qwen CPU embedding compute; under contention, queue wait becomes the dominant addition.

`persistenceMs` is zero in the Python workflow benchmark because it measures the analysis workflow before the Java persistence boundary. It is retained explicitly in `latencyBreakdown` rather than being silently omitted.

## Embedding Concurrency Experiment

Each process loaded the embedding model once, used the same index/query set, disabled cache for strict uncached traffic, and measured 20 concurrent strict calls.

| Embedding concurrency | Strict RPS | Strict P95 | Strict P99 | Queue-wait P95 | Compute P95 | Error rate | Model loads |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 4.95 | 13,637.07 ms | 15,854.37 ms | 13,747 ms | 1,113 ms | 0 | 1 |
| 2 | 4.94 | 14,191.29 ms | 15,901.58 ms | 14,516 ms | 2,046 ms | 0 | 1 |
| 4 | 5.12 | 13,927.80 ms | 15,343.59 ms | 13,977 ms | 3,842 ms | 0 | 1 |
| 8 | 5.75 | 13,079.62 ms | 13,620.72 ms | 11,845 ms | 8,406 ms | 0 | 1 |

`recommendedEmbeddingConcurrency = 1`. Higher gate values do not increase useful CPU-only throughput and worsen either P95 or embedding compute through contention.

The strict-20 resource samples were, respectively, 68.87%, 72.39%, 73.12%, and 74.86% process CPU normalized by logical processors, with 1,666.02 MB, 1,664.97 MB, 1,655.15 MB, and 1,649.57 MB working set. Gate 8 has a slightly better overloaded aggregate P95, but does so by increasing embedding compute P95 7.5x; concurrency 1 remains the stable admission-control default.

## Workload Results

With embedding concurrency 1:

| Workload | 20 callers RPS | P50 | P95 | Error rate |
| --- | ---: | ---: | ---: | ---: |
| Light (BM25-only measurement) | 132.50 | 7.82 ms | 39.39 ms | 0 |
| Strict uncached | 5.08 | 17.50 ms | 13,207.33 ms | 0 |
| Strict cached (prewarmed key) | 100.22 | 164.50 ms | 225.41 ms | 0 |
| Mixed-risk retrieval, uncached | 5.02 | 18.87 ms | 13,514.01 ms | 0 |

The strict cached path avoids vector inference but still evaluates BM25 and workflow logic. The uncached strict path should be admission-controlled instead of being allowed to fan out at 20 concurrent callers.

## Cache Effectiveness

The cache key is `contentRootHash + provider/model identity + topK + normalized query`. Repeating the same normalized query produced a hit (`hits: 1`, `misses: 1`, `size: 1` in the isolated validation); changing Top-K produced a miss. Cache entries only store query vectors and ranked retrieval rows, never final governance decisions.

The cache is synchronized and a malformed transient entry is discarded as a safe miss. The cache is version-isolated by index root hash and provider identity, so policy or model changes do not reuse an old vector.

## BM25 And Dense Serial/Parallel Check

The production path is serial. A six-sample local A/B with cache disabled measured serial P95 707.83 ms versus parallel P95 807.79 ms (parallel was 99.96 ms worse). No parallel implementation was merged: BM25 is already tiny relative to local embedding, while shared concurrency would add contention and state complexity.

## Overload Behavior

An embedding queue timeout produces `OVERLOAD_FALLBACK`, increments `overloadFallbackCount`, and continues with BM25 when available. Reflection then determines whether evidence is sufficient; insufficient evidence remains `human_review`. No queue timeout is allowed to become an automatic pass, and the frontend/API receive the governance state rather than a Python exception.

## Capacity Recommendation

For this measured CPU-only machine:

- `recommendedEmbeddingConcurrency = 1`
- `recommendedStrictConcurrency = 1` for bounded P95; use a queue for excess strict requests
- `recommendedMixedConcurrency = 5` only when strict traffic is rate-limited; otherwise preserve the strict bound
- `recommendedRPS = 5` uncached strict requests/second; cached and light traffic can be substantially higher
- Queue timeout: 30,000 ms; on timeout use BM25 fallback and require human review when evidence remains insufficient
- Practical strict P95 target: <= 1,500 ms at admitted concurrency 1; 20 simultaneous uncached strict calls are an overload case, not a normal SLO

CPU is measured as process CPU time normalized by logical processors and working-set memory is read through the Windows process API; no extra runtime dependency was added to the isolated virtual environment.

## Quality Regression

The complete frozen workflow benchmark passed with the original gold content:

| Check | Result |
| --- | ---: |
| Hybrid Recall@1 / Recall@5 | 0.9667 / 0.9667 |
| Risk F1 | 0.7677 |
| HIGH_RISK_AUTO_PASS_COUNT | 0 |
| requestedMode / actualMode | hybrid / hybrid |
| Provider status | ready |
| Vector count / dimension | 71 / 1024 |
| API errors | 0 |
| Warm strict P95 | 1,013.34 ms |

## Remaining Bottlenecks

Cold model startup and CPU embedding are the limiting costs. The current cache prevents repeated-query embedding work, but it intentionally does not cache governance decisions. CPU/memory telemetry remains a deployment-observability follow-up; it is not represented as a successful measurement in this report.

## Quality Gate Interpretation

Step 19 uses four separate gates so unrelated repository debt cannot invalidate a completed performance and governance regression assessment.

| Gate | Result | Interpretation |
| --- | --- | --- |
| `STEP19_PERFORMANCE_GATE` | PASS | Latency breakdown, concurrency tests, cache validation, overload fallback, capacity recommendation, and this report are complete. |
| `STEP19_REGRESSION_GATE` | PASS | Frozen gold remains unchanged; Hybrid Recall@1/@5 is 0.9667/0.9667, Risk F1 is 0.7677, high-risk auto-pass is 0, API errors are 0, and Step 18 governance tests pass. |
| `STEP19_SCOPE_QUALITY_GATE` | PASS | Python tests, Java governance tests/compile, targeted governance-page ESLint, and production frontend build pass for files in scope. |
| `STEP19_REPOSITORY_BASELINE` | FAIL (pre-existing) | `npm run lint` reports 40 errors and 91 warnings in historical files outside Step 19. This stage did not modify those files, and `git diff --check` is clean. |

`STEP19_OVERALL = PASS_WITH_BASELINE_EXCEPTION`.
