# Agent-RAG Phase 3A.1 Evaluation Integrity

## Metric Schema

- Metric schema version: `2.0.0`
- Benchmark version: `phase3a1-synthetic-fixture-v1`
- Benchmark hash: `46a9b48c9a85fd531cae2a7e8bd0c98831d970580bba898fe65c59020ea786a6`
- Knowledge root hash: `2e30c4224fb250598f6a7adc68b0d6409fbad3bd2e3cbf3883dd87155d6b9c02`

## Definitions

- HitRate@K: macro query-level rate where at least one relevant chunk appears
  in top K.
- Recall@K: macro relevant chunk coverage in top K.
- MRR: mean reciprocal rank of the first relevant result.
- nDCG@5: normalized discounted cumulative gain using benchmark labels.

## Corrected Benchmark

| Mode | HitRate@5 | Recall@5 | MRR | nDCG@5 |
| --- | ---: | ---: | ---: | ---: |
| BM25-only | 0.8833 | 0.4733 | 0.7978 | 0.5504 |
| BGE-M3 Dense-only | 0.4333 | 0.1183 | 0.1800 | 0.1048 |
| Hybrid-real | 0.8833 | 0.4733 | 0.7978 | 0.5504 |

The corrected evaluation shows that this controlled synthetic fixture is
lexically biased. BGE-M3 dense-only is not superior to BM25 on this fixture.
Hybrid-real uses sparse-protected fusion so real dense evidence can participate
without degrading the BM25 baseline.

## Benchmark Integrity

- Case count: `120`
- Documents: `59`
- Chunks: `474`
- Data type: `synthetic controlled fixture`
- Duplicate case count: `0`
- Missing relevant chunk count: `0`
- Cross-tenant label violation count: `0`
- Exact query/chunk match count: `0`
- Unique target token leak count: `0`
- Single-candidate case count: `0`

This benchmark is not real customer data and must not be described as a real
customer benchmark.

## Latency Evidence

- Clock: `perf_counter_ns`
- Sample count: `120`
- Cold start: `25049.746 ms`
- First embedding: `28.476 ms`
- Warm embedding p50/p95/p99: `33.755 / 40.828 / 43.368 ms`
- FAISS p50/p95/p99: `286.2 / 442.6 / 614.6 us`
- Hybrid p50/p95/p99: `70.705 / 82.349 / 84.397 ms`

The old `0 ms` FAISS latency has been superseded by microsecond precision.

## Gate

Phase 3A.1 passed:

- `AGENT_RAG_EVALUATION_FORMULA_PASS`
- `AGENT_RAG_EVALUATION_RANGE_PASS`
- `AGENT_RAG_BENCHMARK_INTEGRITY_PASS`
- `AGENT_RAG_LATENCY_EVIDENCE_PASS`
- `AGENT_RAG_PYTHON_DEPENDENCY_PASS`
- `AGENT_RAG_REAL_DENSE_TEST_COVERAGE_PASS`
- `AGENT_RAG_PHASE3A1_PASS`
