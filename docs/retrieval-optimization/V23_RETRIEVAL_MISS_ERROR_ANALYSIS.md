# V2.3 Retrieval Miss Error Analysis

Phase 9.1 analyzes the existing retrieval-missed answerable cases from the frozen v2.2 benchmark. It does not modify retrieval runtime, BM25, dense retrieval, RRF, chunking, sparse retrieval, multi-vector retrieval, or query expansion.

| Metric | Value |
|---|---:|
| Diagnostic cases | 90 |
| BM25 Top100 hits | 39 |
| Dense Top100 hits | 90 |
| Both Top100 hits | 39 |
| Neither Top100 hits | 0 |
| Union Top100 coverage | 1.0 |
| Candidate K recoverable | 90 |

Primary miss type counts:

```json
{
  "CANDIDATE_K_TOO_SMALL": 90
}
```

Candidate K recovery counts:

```json
{
  "CANDIDATE_K_100_RECOVERABLE": 5,
  "CANDIDATE_K_10_RECOVERABLE": 38,
  "CANDIDATE_K_20_RECOVERABLE": 21,
  "CANDIDATE_K_50_RECOVERABLE": 26
}
```
