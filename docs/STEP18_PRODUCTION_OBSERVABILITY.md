# Step 18 Production Governance Observability

## Event schema

`litemall_ai_governance_observation` stores governance metadata only. It never stores a review body, policy body, token, API key, or embedding. A decision event records route, decision, evidence status, retrieval mode, risk-type codes, bounded citation references, latency, and the workflow/policy/embedding versions. Human-review events add the final decision and one reason code.

Human override reason codes are: `FALSE_POSITIVE`, `WRONG_RISK_TYPE`, `EVIDENCE_INSUFFICIENT`, `EVIDENCE_MISMATCH`, `CONTEXT_MISSING`, `POLICY_NOT_APPLICABLE`, `BUSINESS_EXCEPTION`, and `OTHER`.

## Sampling

Auto-pass QA samples are selected through `POST /admin/ai/risk/qa-sample`; they do not change a business record. QA writes only `correct_pass` or `missed_risk` through `POST /admin/ai/risk/qa-result`.

Light-path shadow audit uses the stable hash of `reviewId` and defaults to 5 percent (`ai.governance-quality.shadow-sample-percent`). A sampled request is re-evaluated through `/api/v1/review/shadow-audit` in an isolated background task. It neither persists a review analysis nor creates a risk task. Only a route/decision disagreement is recorded.

## Dashboard/API

`GET /admin/ai/risk/quality-metrics?hours=24` provides time-window totals, strict-path and human-review rates, human decisions, retrieval fallback/failure counts, per-risk summaries, top override dimensions, and only data-derived alerts. The Risk Review Center presents the core ratios and alerts.

## Alert posture

No hard production thresholds are declared before traffic is observed. The API emits factual alerts for retrieval failures and sampled router disagreements. Operations should establish baseline bands from observed windows before configuring an external alerting system.

## Controlled simulation

The frozen Step 17 fixture is not used as a metrics source. Before production traffic, use separate synthetic rows representing normal, risky, ambiguous, and multi-risk reviews to exercise aggregation, feedback, QA, and shadow-disagreement reporting. Benchmark execution remains separate and must validate SHA-256 `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`.

## Assist-mode invariant

Evidence status `supported` is an AI recommendation, not an automatic high-risk sanction. Human review remains the final decision for high-risk governance tasks.

## Benchmark Configuration Integrity

The local runtime and benchmark CLI both load the git-ignored `ai-service/.env` through `app.core.config`; explicit process environment variables take precedence. Dense/hybrid benchmark modes warm the lazy provider and fail with `BENCHMARK_DENSE_PROVIDER_NOT_READY` if Qwen or FAISS is unavailable. Results record requested and actual mode so fallback cannot be reported as hybrid.

Three fresh complete workflow runs under frozen SHA `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54` each recorded Hybrid Recall@1/@5 `0.9667 / 0.9667`, risk F1 `0.7677`, zero high-risk auto-passes, and zero API errors.
