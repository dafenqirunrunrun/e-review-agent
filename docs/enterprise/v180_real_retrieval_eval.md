# v1.8.0 Real Retrieval Evaluation

Status: `V180_REAL_RETRIEVAL_EVAL_PASS`

## Evidence Boundary

- Real BGE-M3 used: `True`
- FAISS executed: `True`
- Persistent restart verified: `True`
- Hash dense primary path: `False`

## Metrics

### dense_bge_m3_faiss

- hit_at_1: `0.625`
- hit_at_3: `0.9375`
- hit_at_5: `1.0`
- recall_at_5: `1.0`
- mrr: `0.776`
- ndcg_at_5: `0.8327`
- empty_retrieval_rate: `0.0`
- forbidden_top5_hit_count: `24`
- negative_control_false_positive_count: `4`

### sparse_bm25

- hit_at_1: `0.0`
- hit_at_3: `0.0833`
- hit_at_5: `0.0833`
- recall_at_5: `0.0833`
- mrr: `0.0417`
- ndcg_at_5: `0.0526`
- empty_retrieval_rate: `0.9167`
- forbidden_top5_hit_count: `4`
- negative_control_false_positive_count: `0`

### hybrid_bge_m3_bm25_rrf

- hit_at_1: `0.625`
- hit_at_3: `0.9375`
- hit_at_5: `1.0`
- recall_at_5: `1.0`
- mrr: `0.776`
- ndcg_at_5: `0.8327`
- empty_retrieval_rate: `0.0`
- forbidden_top5_hit_count: `24`
- negative_control_false_positive_count: `4`

### hash_dense_negative_control

- hit_at_1: `0.0`
- hit_at_3: `0.1042`
- hit_at_5: `0.125`
- recall_at_5: `0.125`
- mrr: `0.0389`
- ndcg_at_5: `0.0601`
- empty_retrieval_rate: `0.0`
- forbidden_top5_hit_count: `4`
- negative_control_false_positive_count: `4`
