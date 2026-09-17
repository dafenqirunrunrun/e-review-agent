# V2.2 Deterministic Reranker Feature Audit

The deterministic reranker is not a pure same-input cross-encoder baseline.

## Features Used

- Original retrieval rank: yes, through stable tie-breaking after scoring.
- BM25 score: yes, indirectly through `fusionScore`.
- Dense score: yes, indirectly through `fusionScore` when the hybrid candidate came from dense retrieval.
- RRF score: yes, `fusionScore` is the primary score basis.
- Source priority: no explicit source priority in the reranker itself.
- Temporal priority: no explicit temporal priority in the reranker itself; temporal eligibility has already filtered candidates.
- Document status: no scoring boost, but eligibility filtering rejects invalid evidence before reranking.
- Exact keyword overlap: yes, `overlap * 0.01` is added to fusion score.
- Task-specific metadata: yes, through upstream tenant/time/status eligibility and RRF features not visible to the real cross-encoder passage.

## Fairness Observation

The real cross-encoder receives query plus content-only passage. It does not receive fusion score, original RRF rank, source type, title, section title, tenant scope, or effective date. Therefore the deterministic baseline has a task-specific information advantage. This explains part of the measured gap but does not qualify the real reranker.

Current engineering default should remain:

`BAAI/bge-m3 -> deterministic reranker -> Qwen/Qwen3-1.7B`
