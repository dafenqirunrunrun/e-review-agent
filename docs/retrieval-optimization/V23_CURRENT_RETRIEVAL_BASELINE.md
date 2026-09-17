# V2.3 Current Retrieval Baseline

This document freezes the current retrieval baseline on `v23-retrieval-qualification-v1`.

No BM25, dense, RRF, chunking, query, sparse, or multi-vector tuning was performed in Phase 9.0-9.1.

| Metric | BM25 | Dense | RRF | Union Oracle |
|---|---:|---:|---:|---:|
| Recall@10 | 0.333333 | 0.279167 | 0.304167 | 0.320833 |
| Recall@20 | 0.608333 | 0.516667 | 0.525 | 0.579167 |
| Recall@50 | 0.779167 | 0.795833 | 0.745833 | 0.804167 |
| Recall@100 | 0.9 | 0.954167 | 0.891667 | 0.933333 |
| MRR | 0.141386 | 0.127197 | 0.127639 | 0.137152 |
| nDCG@5 | 0.118933 | 0.101291 | 0.096966 | 0.110111 |

Baseline metrics hash: `bf7fc058647c30449b3dde46e4b3b7b61b1f9d807b1dd75df8212b3cf986d429`

This is a frozen comparison baseline for Phase 9.2 experiments. It does not claim retrieval quality improvement.
