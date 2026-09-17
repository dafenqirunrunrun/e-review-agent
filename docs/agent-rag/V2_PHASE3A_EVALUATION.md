# Agent-RAG Phase 3A Evaluation

## Dataset

- Query cases: `120`
- Documents: `59`
- Chunks: `474`
- Tenants: `tenant-a`, `tenant-b`, `tenant-c`, plus `__public__`
- Data type: project-owned synthetic governance knowledge

The dataset covers refund, safety, fraud, logistics, product manual and
customer-service scenarios, with disabled and expired knowledge included for
filtering checks.

## Superseded Phase 3A Values

The first Phase 3A report contained invalid nDCG values above 1, for example
`Hybrid-real nDCG@5=2.9388`. Phase 3A.1 supersedes those values. The root cause
and corrected formulas are documented in
`docs/agent-rag/V2_PHASE3A1_EVALUATION_AUDIT.md`.

## Corrected Results

| Mode | HitRate@5 | Recall@5 | MRR | nDCG@5 | Citation Coverage | Tenant Violations |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25-only | 0.8833 | 0.4733 | 0.7978 | 0.5504 | 1.0000 | 0 |
| BGE-M3 Dense-only | 0.4333 | 0.1183 | 0.1800 | 0.1048 | 1.0000 | 0 |
| BM25 + BGE-M3 | 0.8833 | 0.4733 | 0.7978 | 0.5504 | 1.0000 | 0 |

## Latency

| Metric | Value |
| --- | ---: |
| Build | 28436.894 ms |
| Cold start | 25049.746 ms |
| First embedding | 28.476 ms |
| Warm embedding p50 | 33.755 ms |
| Warm embedding p95 | 40.828 ms |
| Warm embedding p99 | 43.368 ms |
| FAISS p50 | 286.2 us |
| FAISS p95 | 442.6 us |
| FAISS p99 | 614.6 us |
| Hybrid-real p50 | 70.705 ms |
| Hybrid-real p95 | 82.349 ms |
| Hybrid-real p99 | 84.397 ms |

## Resource Evidence

- RSS before: `123 MB`
- RSS after model: `1340 MB`
- RSS after index: `1340 MB`
- CUDA allocated peak: `2206 MB`
- CUDA reserved peak: `2228 MB`

These are local single-machine measurements and are not production SLOs.
Latency uses `perf_counter_ns`; sub-millisecond FAISS timings are reported in
microseconds.

## Phase 3A.2 Follow-up

Phase 3A.2 supersedes the open dense-quality question from Phase 3A.1. It does
not replace the corrected Phase 3A.1 baseline above; it adds a stratified
diagnostic benchmark.

Key Phase 3A.2 result:

```text
AGENT_RAG_DENSE_SEMANTIC_GAIN_ONLY
```

Evidence:

- BGE-M3 provider health passed.
- FAISS numpy-vs-index numerical correctness passed.
- The expanded benchmark has `174` cases:
  lexical `54`, semantic `54`, mixed `36`, temporal `10`,
  tenant-isolation `10`, no-answer `10`.
- Evaluation split has `122` cases after calibration split.
- Overall evaluation still does not show BGE-M3 beating BM25.
- Semantic subset shows BGE-M3/hybrid signal where BM25 has no relevant top-5
  hits.
- Hybrid equality with BM25 is explained by sparse top-5 protection in the
  runtime.

Recommended default after Phase 3A.2:

```text
RAG_DEFAULT_RETRIEVAL_MODE=bm25-first-semantic-hybrid
```
