# V2.3 Retrieval Engineering Evidence

## Resume Version

Built a BM25 + BGE-M3 Dense hybrid retrieval baseline with RRF, deterministic reranking and evidence eligibility governance. Designed a 375-case Benchmark split into Calibration/Evaluation/Challenge gates. Evaluated Sparse, real reranker and Parent-aware Fusion candidates; when held-out Evaluation failed to generalize, blocked runtime promotion and preserved reproducible candidate/ranking hash evidence and bad-case analysis.

## Metrics Version

Parent-aware Calibration improved Coverage@20 from 70.00% to 76.67%, but one-time held-out Evaluation dropped from 65.00% to 63.33%; the route was rejected by quality gates. BGE-M3 Sparse completed runtime and stability experiments but was closed because no stable sparse encoding configuration was identified.

## Interview Story

The core engineering decision was to treat negative results as production-safety evidence: do not retune after Evaluation, do not consume Challenge, and do not promote experimental routes into runtime defaults.
