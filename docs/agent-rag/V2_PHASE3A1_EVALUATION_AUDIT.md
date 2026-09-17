# Agent-RAG Phase 3A.1 Evaluation Audit

## Finding

The original Phase 3A evaluation reported `Hybrid-real nDCG@5=2.9388`.
That value is mathematically invalid because standard nDCG must be in the
closed interval `[0, 1]`.

## Root Cause

The old implementation accumulated DCG-like gain per query but did not divide
by IDCG for the same query. It also used topic matches as a direct gain list
without a normalized ideal ranking. As a result, multiple relevant results in
the top 5 could produce values greater than 1.

The old calculation did not concatenate all queries into one global list; the
main error was missing IDCG normalization. The old value is superseded and must
not be used as retrieval quality evidence.

## Latency Finding

The original Phase 3A report showed `FAISS p50/p95 = 0 ms / 0 ms`. FAISS search
was real, but the measurement rounded sub-millisecond durations to integer
milliseconds. Phase 3A.1 now records `perf_counter_ns`, microseconds and
fractional milliseconds.

## Dependency Finding

`pip check` failed because Python 3.10 with `pytest 8.3.5` required `tomli`, but
`tomli` was missing as a top-level package. Network installation through pip and
conda was blocked by TLS EOF/SSL errors. The active environment was repaired
offline using the same environment's vendored `tomli` package and dist-info, and
`tomli>=2.0,<3.0; python_version < "3.11"` was added to the test/runtime setup
requirements file.

## Correct Formula

```text
DCG@K = sum((2^rel_i - 1) / log2(i + 2))
nDCG@K = DCG@K / IDCG@K
```

If `IDCG=0`, nDCG is defined as `0`.

Relevance comes from benchmark labels:

- binary relevance: relevant `1`, irrelevant `0`
- forbidden chunks: relevance `0`

Raw BM25, cosine, RRF and reranker scores are not used as relevance labels.
