# Agent-RAG Phase 3A.2 Fusion Calibration

## Calibration Method

Allowed strategies were intentionally limited to simple auditable fusion:

- RRF
- weighted RRF

Weighted RRF grid:

| Sparse weight | Dense weight |
| ---: | ---: |
| 1.0 | 0.5 |
| 1.0 | 1.0 |
| 1.0 | 1.5 |
| 0.5 | 1.0 |

Selection metric:

```text
overall.hybrid.ndcgAt5 on calibration set
```

Selected configuration:

```text
strategy=weighted-rrf-with-bm25-protected-top5-runtime
sparseWeight=1.0
denseWeight=0.5
rrfK=60
```

## Fusion Contribution

Evaluation evidence:

- dense contribution rate: `0.4590`
- dense unique top-K rate: `0.7377`
- hybrid changed top-K rate: `0.1967`
- hybrid improved query count: `7`
- hybrid degraded query count: `0`

Dense candidates are present and often unique, but the runtime protects sparse
top-5 before appending dense-only candidates. This is why Phase 3A hybrid could
exactly match BM25 on top-5.

## Dense Top-K Sensitivity

| Dense Top-K | BGE Recall@5 | BGE nDCG@5 | Hybrid Recall@5 | Hybrid nDCG@5 |
| ---: | ---: | ---: | ---: | ---: |
| 5 | 0.0393 | 0.0321 | 0.1443 | 0.1588 |
| 10 | 0.0410 | 0.0333 | 0.1443 | 0.1588 |
| 20 | 0.0410 | 0.0333 | 0.1443 | 0.1588 |
| 50 | 0.0410 | 0.0333 | 0.1443 | 0.1588 |

Increasing dense Top-K beyond 10 does not materially improve top-5 metrics. The
main limitation is not simply candidate count.

## No-answer Gate

No-answer evaluation:

- no-answer cases in evaluation: `7`
- false evidence rate: `0.0`
- correct rejection rate: `1.0`

The evidence quality gate rejects low-score neighbors instead of treating every
FAISS nearest neighbor as valid evidence.

Gate:

```text
AGENT_RAG_NO_ANSWER_EVIDENCE_PASS
AGENT_RAG_FUSION_CALIBRATION_PASS
```
