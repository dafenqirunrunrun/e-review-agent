# Agent-RAG Phase 3A.3 Provider Evaluation

## Fixed Inputs

- benchmark version: `phase3a2-stratified-v1`
- benchmark hash:
  `440a575c325442263ae0b63b039c95c79e35ee8efcc3875284c2af1274ac8454`
- knowledge root hash:
  `9641d3406c7ee452c0f2bc77c7edfc6f4e546c582e33577c91d497fe427ce225`
- evaluation case hash:
  `16e55999a3305e0c9123ce73f3e940846e678ea45b6aaf93947acc29096e778c`
- fusion config hash:
  `0abe1c700dbb39371b7233e77e807a0c96fce917537f73f11fb542e41f716c1c`

The benchmark and fusion parameters were not changed to favor any provider.

## Provider Status

| Provider | Status |
| --- | --- |
| Legacy CLS | PASS |
| FlagEmbedding | BLOCKED |
| Sentence Transformers | BLOCKED |

FlagEmbedding and Sentence Transformers are blocked by missing dependencies due
TLS/SSL download failures. Their quality metrics are not reported as if they ran.

## Legacy CLS Metrics

Overall:

| Mode | HitRate@5 | Recall@5 | MRR | nDCG@5 |
| --- | ---: | ---: | ---: | ---: |
| BM25 | 0.2295 | 0.1295 | 0.2057 | 0.1444 |
| Legacy Dense | 0.1639 | 0.0410 | 0.0538 | 0.0333 |
| Legacy Hybrid | 0.2869 | 0.1443 | 0.2322 | 0.1588 |

Sanity:

| Provider | Cases | Pairwise Acc | Positive-Hard Margin |
| --- | ---: | ---: | ---: |
| Legacy CLS | 30 | 1.0000 | 0.241804 |
| FlagEmbedding | 30 | BLOCKED | BLOCKED |
| Sentence Transformers | 30 | BLOCKED | BLOCKED |

Resource:

| Provider | Cold start | Warm p50 | Warm p95 | Throughput | RSS after model | CUDA peak |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Legacy CLS | 6315.096 ms | 81.905 ms | 164.755 ms | 121.749/s | 1406 MB | 2191 MB |
| FlagEmbedding | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |
| Sentence Transformers | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |

## Index E2E

| Scenario | Status |
| --- | --- |
| Legacy index + Legacy provider | PASS |
| Flag provider activating Legacy index | PASS, rejected |
| Flag index + Flag provider | BLOCKED |
| Legacy provider activating Flag index | BLOCKED because Flag index unavailable |

The compatibility code is present, but full Flag index validation requires the
FlagEmbedding dependency.

## Phase 3A.3.2 Evaluation Update

The official FlagEmbedding provider and its matching FAISS index now execute
successfully in the isolated validation environment.

Provider status:

| Provider | Status |
| --- | --- |
| Legacy CLS | PASS |
| FlagEmbedding | PASS |
| Sentence Transformers | BLOCKED: reference asset compatibility |

Overall nDCG@5:

| Provider | Dense | Hybrid |
| --- | ---: | ---: |
| Legacy CLS | 0.0333 | 0.1588 |
| FlagEmbedding | 0.0333 | 0.1588 |
| Sentence Transformers | not executed | not executed |

Semantic subset nDCG@5:

| Provider | Dense | Hybrid |
| --- | ---: | ---: |
| Legacy CLS | 0.0428 | 0.0428 |
| FlagEmbedding | 0.0428 | 0.0428 |
| Sentence Transformers | not executed | not executed |

Sanity fixture:

| Provider | Pairwise Acc | Positive-Hard Margin |
| --- | ---: | ---: |
| Legacy CLS | 1.0000 | 0.241804 |
| FlagEmbedding | 1.0000 | 0.241787 |
| Sentence Transformers | BLOCKED | BLOCKED |

Resource benchmark:

| Provider | Cold start | Warm p50 | Warm p95 | Throughput | CUDA peak |
| --- | ---: | ---: | ---: | ---: | ---: |
| Legacy CLS | 2164.394 ms | 66.424 ms | 69.408 ms | 209.726/s | 2191 MB |
| FlagEmbedding | 1796.743 ms | 74.159 ms | 117.210 ms | 139.848/s | 2191 MB |
| Sentence Transformers | BLOCKED | BLOCKED | BLOCKED | BLOCKED | BLOCKED |

Quality conclusion:

```text
AGENT_RAG_OFFICIAL_PROVIDER_PARITY_ONLY
```

The official provider is now runtime-valid and fingerprint-valid, but the fixed
benchmark does not show quality improvement over the legacy dense path.
