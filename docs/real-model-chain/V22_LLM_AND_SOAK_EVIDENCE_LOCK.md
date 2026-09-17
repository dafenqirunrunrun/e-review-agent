# V2.2 LLM And Soak Evidence Lock

This document freezes the already-passed real LLM quality evidence and 1800-second real model-chain soak evidence before Phase 8.4 reranker recovery work.

## Source

- Source commit: `57858817`
- LLM quality decision: `PASS`
- LLM boundary: `REAL_LLM_QUALITY_VERIFIED`
- Soak status: `PASS`
- Reranker boundary at lock time: `MODEL_RERANKER_NOT_VERIFIED`

## Model Assets

| Component | Model | Revision | Fingerprint | License | Files | Bytes |
| --- | --- | --- | --- | --- | ---: | ---: |
| Embedding | `BAAI/bge-m3` | `external-existing` | `a36441812a43bc60e2464af3cc3ffc4d466fc2dc9a52d921264b0109c39094a2` | `MIT` | 10 | 4564380154 |
| Reranker | `BAAI/bge-reranker-v2-m3` | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` | `cf87d1dfe5081feb734ff8635b7781f3f77c4bab3939ffba3a6d16a653611e82` | `Apache-2.0` | 14 | 1134700145 |
| LLM | `Qwen/Qwen3-1.7B` | `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` | `315d7ccccc6acdbb0d5ee535a292936c3d2306aa7a06817f51b40b734af10628` | `Apache-2.0` | 14 | 4079451553 |

Local asset paths are intentionally omitted from this committed document.

## Frozen Hashes

- Benchmark hash: `222802bed4ac363db5dbdfba5b362584ff05e2788f606781bfa2cfbb7e39a0b6`
- Knowledge hash: `6a47565e19594a6c527df10e34c63af004a6080f80f1817d697d28e828746a94`
- Calibration hash: `5b49e660cc2d2186abdbed642fcae70ba9e8e7c4cd56b1c7c1262887c4dd608b`
- Evaluation hash: `16e55999a3305e0c9123ce73f3e940846e678ea45b6aaf93947acc29096e778c`
- Soak summary SHA256: `8dcd45f444f11ae0f4c0cc2743a84e7f7dd4ef9344df3ff3647d80dd64746b4e`
- LLM quality summary SHA256: `db58658f413687022c5958c471f26e22418dcd84cc89c1a5b037730594bb03f9`
- LLM gate SHA256: `92945111d3c6d12c54145e9b95ad24961e9ed8458041fd0a19473b7b6ad96d2d`
- Reranker benchmark summary SHA256: `cb7d7f5cf3ec783bffd9d33dcbe4625ecbb0ef8f1dc5908fc875ec3a82625529`

## Soak Evidence

- Duration: `1803` seconds
- Requests: `35`
- Successes: `35`
- Real BGE executions: `35`
- Real reranker executions: `35`
- Real LLM executions: `35`
- Fallback count: `0`
- Unhandled errors: `0`
- Unexpected OOM: `0`
- Latency p50/p95/p99: `40906.958` / `45808.583` / `47156.894` ms
- CUDA start/peak/end: `2174.06` / `3466.0` / `2174.06` MB
- Model load/evict/switch: `425` / `424` / `424`
- Stability decision: `PASS_CANDIDATE`

## LLM Quality Evidence

- Case count: `250`
- Dataset hash: `af1a32796ca7107b44846095f2b561835e02d5441f017fd74cfdb878fddb5508`
- Schema valid rate: `1.0`
- Grounded rate: `1.0`
- Tenant violations: `0`
- Prompt-injection unsafe executions: `0`
- PII leaks: `0`
- Real generate executions: `200`
- Fallback executions: `25`

## Boundary

This lock does not claim reranker quality verification. At this point the system remains `MODEL_RERANKER_NOT_VERIFIED` and `AGENT_RAG_V22_REAL_MODEL_CHAIN_BLOCKED`.
