# Step 22 Final Acceptance Report

## Result

```text
STEP22_FINAL_ACCEPTANCE_GATE = PASS
```

The accepted scope is the personal, free-local E-Review Agent demo. This is an evidence-backed assisted-review system, not an autonomous punishment engine or a production availability claim.

No Router, Safety Gate, Policy RAG, frozen gold, Agent graph, or Fast Eligibility policy was changed during Step 22. Fast Eligibility remains disabled by default.

## Accepted Business Path

```text
Real review
  -> Intent Router and Safety Gate
  -> Planner / Execution
  -> hybrid Policy Retriever
  -> EvidenceAgent
  -> ReflectionAgent
  -> decision or manual review
  -> idempotent human resolution
  -> audit record and reviewer-facing citation
```

The real Admin-to-AI path was executed with one ordinary review and one risk review. The risk case produced four risk types, three valid policy citations, a partial-coverage mismatch, and a manual-review task. The first human action closed the task; the second identical submission returned the existing terminal result. Re-analysis reused the same analysis snapshot. Synthetic acceptance fixtures were removed; the storefront E2E records below are retained as an inspectable business trace.

## Reboot Recovery And Storefront E2E

After a full machine reboot, all six local dependencies were restarted and the storefront path was executed through the real UI:

```text
Product 1181000
  -> order 66 / 20260910793152
  -> demo payment and shipment
  -> receipt
  -> comment 1084
  -> scheduled automatic audit
  -> analysis 336 / agent run 135
  -> risk tasks 495 and 496
  -> task 495 human override
  -> closed with one audit log, one feedback row, and one observation row
```

The review text combined a five-star screenshot cashback offer, review suppression, product damage, and delayed after-sales handling. The workflow ran Router, Planner, Execution, hybrid Policy Retrieval, Evidence, Reflection, Replan, a second Evidence/Reflection pass, and Finalize. Reflection reported `PARTIAL_RISK_COVERAGE`: three risks were supported while `after_sales_risk` lacked direct policy coverage, so the result safely entered human review.

Five runtime blockers were found and fixed without changing Router or RAG policy:

- The H5 development proxy now defaults to the actual wx API port `8082` and remains environment-overridable.
- Storefront SKU selection now submits the real product-row identifier instead of deriving an invalid ID from display values.
- Java payloads with `ratingSource=null` are normalized safely, while `UNKNOWN` ratings cannot create a false `LOW_RATING` signal.
- `litemall_ai_agent_run.rag_strategy` was widened from 32 to 64 characters so the stable value `policy_rag_hybrid_with_bm25_fallback` persists without truncation.
- Nested dense-provider readiness metadata now redacts the local embedding model path instead of exposing a machine-private absolute path.

Focused live boundary checks passed:

| Case | Expected safe behavior | Result |
| --- | --- | --- |
| Normal five-star review | short path / auto pass | PASS |
| Historical default `rating=1`, source `UNKNOWN` | no `LOW_RATING` | PASS |
| Real one-star rating | `LOW_RATING` and governance path | PASS |
| Five-star cashback | no auto pass; policy-backed human review | PASS |
| Delete-negative-review demand | no auto pass; policy-backed human review | PASS |
| Empty text, rating 0, rating 6 | HTTP 422 | PASS |
| Duplicate human submission | terminal result reused | PASS |
| Re-analysis of comment 1084 | analysis 336 reused; human result preserved | PASS |
| Public readiness metadata | local model path redacted; hybrid remains ready | PASS |

## Runtime Gate

| Component | Port | Result |
| --- | ---: | --- |
| MySQL | 3306 | listening and persistence checks passed |
| Storefront H5 | 6255 | product-to-comment flow passed |
| AI service | 8008 | ready |
| wx API | 8082 | listening and responsive |
| Admin API | 8083 | login and review API passed |
| Admin UI | 9527 | reviewer flow passed |

Policy retrieval reported `actualMode=hybrid`, Qwen provider `ready`, 71 vectors, dimension 1024, and BM25 fallback available. The local embedding path is represented as `configured` in public readiness configuration rather than exposed as an operator-facing value.

## Frozen Benchmark

Frozen gold SHA-256:

```text
9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54
```

The SHA was checked before and after execution and did not change.

| Metric | Result |
| --- | ---: |
| Cases | 120 |
| Policy retrieval cases | 90 |
| BM25 Recall@1 | 0.8556 |
| Dense Recall@1 | 0.8333 |
| Hybrid Recall@1 | 0.9667 |
| Hybrid Recall@5 | 0.9667 |
| Hybrid MRR | 0.9667 |
| Risk precision / recall / F1 | 0.7438 / 0.7933 / 0.7677 |
| Route accuracy | 0.9417 |
| Decision accuracy | 0.8833 |
| Reflection accuracy | 0.8083 |
| Human-review F1 | 0.9333 |
| Normal-review auto-pass | 9/10, 0.9000 |
| High-risk auto-pass count | 0 |
| API errors | 0 |

Warm P95 was 29.16 ms for hybrid retrieval, 30.54 ms for normal analysis, and 40.48 ms for strict analysis. All normal, strict, and repeated-strict concurrency runs at 1, 5, 10, and 20 concurrent requests had zero errors and zero timeouts.

All nine fault-injection scenarios passed: Qwen unavailable, FAISS unavailable, policy chunks missing, AI timeout, retrieval exception, database-write coverage, duplicate human review, incomplete citation, and legacy v1 snapshot adaptation.

## Verification Matrix

| Check | Result |
| --- | --- |
| Python workflow/RAG/API/runtime tests | 105 passed |
| Reboot-recovery focused Python regression | 48 passed |
| Readiness path-redaction regression | 11 passed |
| Java governance and human-review tests | 6 passed |
| Java package for wx/admin APIs | PASS |
| Frontend unit tests | 8 passed |
| Targeted reviewer/storefront ESLint | PASS |
| Admin and storefront production builds | PASS, existing deprecation/order/size warnings |
| `git diff --check` | PASS |
| Database orphan/stale consistency checks | PASS, all counts 0 |
| `.env` ignore and tracked secret scan | PASS |

The repository-wide legacy lint command still reports 40 errors and 91 warnings in unrelated historical files. The reviewer-facing files changed by the governance work pass direct targeted ESLint, and the production build passes. This debt is recorded rather than hidden and does not alter the Step 22 business Gate.

## Browser Acceptance

The browser path passed:

```text
评论治理中心
  -> 审核工作台
  -> 人工复核
  -> 风险任务详情
  -> Reflection
  -> Policy Evidence
  -> 查看原始政策
  -> 最终人工处理结果
```

The reviewer saw Chinese risk names and per-risk evidence coverage, a readable mismatch explanation, bounded evidence snippets, source level and section path, and the persisted reviewer/time/result. Technical retrieval fields remained collapsed. Clicking the citation opened the exact Google Maps policy URL, which also returned HTTP 200.

## Release Controls

- AI recommendations remain distinguishable from final human action.
- Evidence absence, mismatch, incomplete citation, or retrieval failure cannot produce a fabricated citation or silent strong action.
- Human terminal decisions are idempotent and are not overwritten by later analysis.
- Dense failure retains BM25 fallback; total retrieval failure routes to human review.
- Fast Eligibility is shipped default-off and falls back to the baseline chain on any policy-integrity problem.
- Local `.env`, model paths, credentials, and raw review content are excluded from committed acceptance artifacts.
- Langfuse remains optional and fail-open; it is not a business decision dependency.

## Remaining Limits

1. Risk F1 `0.7677` is adequate for this controlled demo Gate but not a basis for autonomous enforcement.
2. The frozen set is project-maintained controlled data, not an independently annotated production sample.
3. The legacy frontend has repository-wide lint debt and a 1.39 MiB entrypoint size warning.
4. Authenticated Langfuse trace inspection remains a manual observability check; runtime failure isolation has already passed.
5. Real production rollout would still require independent annotation, access control hardening, privacy review, backup/recovery rehearsal, and monitored canary operation.
6. One multi-risk analysis currently fans out into separate operational task rows. Resolving task 495 does not automatically resolve sibling task 496; this preserves current per-task semantics but adds reviewer effort and needs a later product decision about grouped resolution.
7. Druid successfully replaces long-idle MySQL connections, but the current pool logs those recoverable discards at `ERROR`; production log severity and idle-validation settings should be tuned.

## Artifacts

- Full benchmark: `ai-service/artifacts/step22/frozen_benchmark.json`
- Machine-readable Gate: `ai-service/artifacts/step22/final_acceptance_gate.json`
- Startup and recovery guidance: `docs/LOCAL_RUNBOOK.md`
