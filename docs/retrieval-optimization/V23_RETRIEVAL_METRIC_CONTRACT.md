# V2.3 Retrieval Metric Contract

Phase 9.2 separates Raw Union Oracle, Union Budgeted and RRF metrics.

The old report showed Dense Recall@100 `0.954167` greater than reported Union Oracle@100 `0.933333`. This was a metric naming problem: the old Union value was ranked/budgeted, not raw union.

Corrected contract:

- Raw Union Oracle@K = BM25 TopK union Dense TopK, not truncated to K after union.
- Union Budgeted@N = raw union sorted by explicit min-rank rule and truncated to N.
- RRF@N = BM25 and Dense fused by reciprocal rank fusion and truncated to N.
- Recall and Coverage are reported separately.
- No-answer cases are excluded from answerable recall and reported separately.

Corrected Raw Union Coverage@100: `0.975`

Corrected RRF Coverage@100: `0.7125`

Gate status: `PASS`
