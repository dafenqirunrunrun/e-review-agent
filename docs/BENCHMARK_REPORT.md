# Step 16 Benchmark Report

## Scope and Runtime

Measured on 2026-09-07 against the local FastAPI service at `127.0.0.1:8008`, not an in-process substitute. The running service reported `review-governance-v2`, 71 policy chunks, Qwen `Qwen/Qwen3-Embedding-0.6B` through the local Transformers provider on CPU, FAISS ready, `retrievalMode=hybrid`, and BM25 fallback available.

Ollama contained `qwen2.5:7b` and `bge-m3:latest`. `qwen2.5:7b` is a generation model and was not used as an embedding model. The benchmark used a local Hugging Face `Qwen3-Embedding-0.6B` directory outside Git, producing 1024-dimensional vectors.

The service was restarted from current source before the gate. The original stale listener was PID 43300; the final controlled restart replaced listener PID 18712 with PID 52972. The post-restart readiness observation completed within approximately 14 seconds; the exact cold-start timer was blocked by the desktop execution policy, so that observation must not be read as a precise cold-start SLO. The first strict request after restart took 1,792 ms and returned v2, `supported`, and three real citations.

## Dataset

`ai-service/data/benchmarks/review_governance_gold_v1.jsonl` contains 120 fixed, project-maintained, rule-grounded controlled gold cases. It is a regression/canary corpus, not an external or independently annotated production dataset. Each case records review text, expected risks, route, decision, reflection status, human-review requirement, and expected evidence tags.

The 12 equally sized categories are normal review, fake review, paid review, rating manipulation, review suppression, after-sales risk, negative review, ambiguous short input, privacy, harassment, multi-risk, and lexical mismatch. Chinese, English, and cross-language cases are explicitly tagged.

## Retrieval Results

90 governance cases with expected policy tags were evaluated. A hit means a returned chunk has an expected risk type or evidence tag.

| Mode | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: |
| BM25 | 0.8556 | 0.9556 | 0.9667 | 0.9022 |
| Dense Qwen + FAISS | 0.8333 | 0.9444 | 0.9556 | 0.8837 |
| Hybrid RRF | 0.9667 | 0.9667 | 0.9667 | 0.9667 |
| BM25 fallback | 0.8556 | 0.9556 | 0.9667 | 0.9022 |

Hybrid Recall@1 improves over BM25 by 11.11 percentage points and over dense-only by 13.33 points. It is not an excuse to change the gold set: all modes used the same 90 queries.

| Hybrid subset | Recall@1 | Recall@3 | Recall@5 | MRR |
| --- | ---: | ---: | ---: | ---: |
| Chinese | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| English | 0.8800 | 0.8800 | 0.8800 | 0.8800 |
| Cross-language | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Lexical mismatch | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Multi-risk | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

The English subset is the retrieval weakness to investigate next; no reranker or retrieval tuning was introduced in this stage.

## Governance Results

All 120 requests completed without API errors.

| Metric | Result |
| --- | ---: |
| Risk-type micro precision / recall / F1 | 0.6392 / 0.4133 / 0.5020 |
| Route accuracy | 0.6333 |
| Decision accuracy | 0.5750 |
| Reflection-status accuracy | 0.8000 |
| Human-review precision / recall / F1 | 0.9091 / 0.6667 / 0.7692 |
| Expected-human-review cases incorrectly auto-passed | 16 |

The final row is a release blocker for automated high-risk disposal. Typical misses are paraphrased fake-review and review-suppression language not covered by the rule intent router, for example organized template reviews or removal-pressure wording that lacks an exact current keyword. The system has good precision when it requests human review, but insufficient recall.

The full confusion matrix and top 15 bad cases are retained in `ai-service/artifacts/step16/benchmark_results.json`. Main observed confusion: `fake_review` is often routed to `normal_review`; `review_suppression` is sometimes missed or classified as after-sales/harassment; low-rating after-sales cases can gain a `negative_review` secondary risk.

## Performance and Concurrency

Warm single-process measurements in milliseconds:

| Stage | Avg | P50 | P95 | P99 | Max |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 retrieval | 9.79 | 9.83 | 10.47 | 10.47 | 10.47 |
| Dense embedding + FAISS | 1371.03 | 1406.29 | 1463.46 | 1463.46 | 1463.46 |
| Hybrid retrieval | 1411.55 | 1389.69 | 1556.62 | 1556.62 | 1556.62 |
| Reflection | 0.06 | 0.04 | 0.28 | 0.28 | 0.28 |
| Normal analyze | 23.36 | 18.04 | 31.72 | 31.72 | 31.72 |
| Strict analyze | 1789.37 | 1777.06 | 1857.87 | 1857.87 | 1857.87 |

At 20 concurrent normal reviews, P95 was 200.53 ms with no errors. At 20 concurrent strict reviews, P95 was 41,305.88 ms with no errors and throughput 0.484 RPS. This is expected queueing for a single CPU Qwen embedding model, but it is not suitable for high-concurrency strict processing.

There is deliberately no API result cache. Repeating the same strict review still produced one retrieval step (first 1, second 1), with cache-hit rate 0 and zero saved embedding/retrieval calls. The FAISS index and loaded model are reused in-process, while results are recomputed so a new policy-index version cannot return stale evidence.

## Fault Injection

All nine non-destructive scenarios passed: Qwen unavailable -> BM25 fallback; FAISS unavailable -> BM25 fallback; missing policy evidence -> human review; caller timeout is observable for admin-api degradation; retrieval exception -> insufficient evidence/human review; DB-write and duplicate-review protections are covered by their transaction/idempotency tests; invalid citation -> insufficient; and v1 snapshots adapt to v2.

Failure policy is fail-closed for a final decision write failure, policy evidence absence, citation invalidity, or reflection mismatch. Dense/FAISS failure may use BM25 only. No fallback may fabricate a citation.

## SLO and Release Decision

These are local-demo SLO candidates based on this measurement, not production promises:

- Availability: API request error rate <= 1% for the controlled canary set. Observed 0%.
- Normal route latency: warm P95 <= 250 ms at 20 concurrent requests. Observed 200.53 ms.
- Strict route latency: warm P95 <= 2,500 ms only at concurrency 1. Observed 1,857.87 ms. Strict concurrency must be admission-controlled to 1 on this CPU host.
- Fallback: dense/FAISS failure fallback success = 100% in the two controlled cases.
- Governance quality gate: high-risk false-negative count must be 0 in the fixed gold corpus before enabling autonomous high-risk action. Observed 16, so this gate FAILS.

Step 16 therefore passes as a measurement and reliability baseline, but does **not** pass the quality gate for production autonomous enforcement. The next work should improve/validate intent-routing coverage for the recorded false negatives, then rerun this exact frozen corpus without editing its expected labels.

## Step 17: Intent Router Safety Convergence

### Frozen Input and Root Cause

The Step 16 gold fixture remains unchanged. Its SHA-256 is `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`, and both the Step 17 ablation and final runtime benchmark fail before measurement if the hash differs.

The pre-change root-cause report is `ai-service/artifacts/step17/baseline_fn_root_cause.json`. All 16 high-risk auto-passes were `ROUTER_FALSE_NEGATIVE`: every case entered `low_touch` with `NO_RISK_SIGNAL` and router confidence 0.88. There were no detector-stage or decision-stage auto-pass failures in this set. Root-cause groups were review-suppression paraphrases (5), privacy expressions (7), harassment expressions (2), and multi-risk expressions (2).

### Change

The router now has two small, independently configurable local safeguards:

- Rule enhancements recognize bounded semantic paraphrases for fabricated reviews, rating incentives, suppression, privacy, and abuse.
- The high-risk safety gate only prevents direct auto-pass. It routes uncertain incentive/review, deletion-for-refund, insider-review, privacy, and abuse combinations into the existing strict governance path. Evidence retrieval and Reflection still decide whether evidence supports a recommendation or requires human review.

No policy source, embedding model, RAG index, reranker, Agent Graph, or human-review state machine changed.

### Ablation on the Same 120 Cases

| Variant | Risk F1 | High-risk auto-pass | High-risk recall | Strict-route rate | Normal auto-pass |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 0.5556 | 16 | 0.7333 | 0.5167 | 0.9000 |
| Router enhancements only | 0.7206 | 0 | 1.0000 | 0.7667 | 0.9000 |
| Safety gate only | 0.7636 | 5 | 0.9167 | 0.7083 | 0.9000 |
| Router + safety gate | 0.8095 | 0 | 1.0000 | 0.8083 | 0.9000 |

The combination is selected. It does not send all reviews to human review: normal-review auto-pass remains 90%, while the higher strict-path rate is attributable to newly recognized risk semantics.

### Final Real Runtime Regression

The final measurement used the restarted current 8008 service with local Qwen dense + FAISS hybrid enabled and the frozen hash argument. Results: risk micro precision/recall/F1 `0.7438 / 0.7933 / 0.7677`; route accuracy `0.9417`; decision accuracy `0.8833`; reflection accuracy `0.8083`; human-review precision/recall/F1 `0.9333 / 0.9333 / 0.9333`; high-risk auto-pass `0`; API errors `0`.

Per-risk F1: fake review `0.8636`, rating manipulation `0.8333`, review suppression `0.7179`, privacy `0.9091`, harassment `0.7692`, after-sales `0.7391`. The remaining bad cases are primarily incomplete multi-label coverage or conservative manual-review outcomes, not silent high-risk auto-passes.

Policy retrieval did not regress: hybrid Recall@1/@5 remained `0.9667 / 0.9667`; BM25 fallback remained available; all 9 fault-injection checks passed. The main remaining trade-off is a strict-route rate of 80.83% on this intentionally risk-heavy controlled corpus. Monitor that rate on representative production traffic before widening autonomous low-risk action.

**Safety conclusion:** the frozen-corpus safety gate now passes because no expected-human-review case is silently auto-passed. This supports evidence-backed assisted review. It is not an authorization to remove human confirmation for high-risk governance actions.

## Step 18 Final Configuration Gate

The Step 18 retrieval regression was a CLI configuration mismatch: 8008 had a PowerShell-injected Qwen model path while fresh benchmark processes did not, causing dense/hybrid to fall back to BM25. The shared config now loads the local, git-ignored `.env`; explicit environment values still win. Dense/hybrid modes fail fast if provider or FAISS is not ready and report requested versus actual mode.

Three fresh complete 120-case runs passed: BM25 Recall@1 `0.8556`, dense Recall@1 `0.8333`, Hybrid Recall@1/@5/MRR `0.9667 / 0.9667 / 0.9667`; actual mode was `hybrid`, provider was `ready`, vector count `71`, dimension `1024`, risk F1 `0.7677`, high-risk auto-pass `0`, and API errors `0` on every run.
