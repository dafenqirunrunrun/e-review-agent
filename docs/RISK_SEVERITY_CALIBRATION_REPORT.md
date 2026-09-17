# Step 21.2 Risk Severity & Confidence Calibration

## Problem Definition

Step 21.2 adds deterministic consequence severity and calibrated classification confidence as observational routing inputs. It does not change Policy RAG, Reflection, Human Review, Safety Gate, or the current governance decision.

## Severity vs Confidence

Severity answers how serious the business consequence would be if a detected risk is real. Confidence estimates whether the current risk classification is correct. A high-severity ambiguous manipulation case may therefore have low confidence; a normal review may have high confidence and low severity.

## Severity Registry

Registry version: `risk-severity-registry-v1`.

| Base severity | Risk types |
| --- | --- |
| LOW | `normal_review` |
| MEDIUM | `after_sales_risk`, `negative_review`, `rating_conflict`, `modality_conflict`, `low_confidence`, `fake_review_suspected`, `other` |
| HIGH | `fake_review`, `paid_review`, `rating_manipulation`, `review_suppression`, `privacy_risk`, `harassment_or_abuse`, `safety_or_fraud_risk` |

Deterministic modifiers cover explicit incentives, organized manipulation, multiple high-risk types, immediate-harm context, and supported policy evidence. Multiple high-risk types, organized high-impact manipulation, or immediate-harm context can raise HIGH to CRITICAL.

## Calibration Dataset

- Dataset: `router-calibration-v1`
- Cases: 240
- Train/calibration: 170; validation: 70, stable stratified 70/30 split
- Source: 240 controlled synthetic cases
- Labels: 240 `synthetic_weak_label+deterministic_registry`; human-reviewed cases: 0
- Difficulty: 120 easy, 96 medium, 24 hard
- Frozen overlap: 0 by normalized text SHA-256
- Dataset SHA-256: `91712F0F156EAACC9FC1AFE9D2D0ABB3B082541FA4BBE0E22CD6A5BEFCF5D1B9`

The separate frozen 120-case set was not used for fitting, threshold selection, or severity rule tuning.

## Small Model

The evaluated production path is the existing lightweight rule-backed Intent Router, exposed through the fixed `small-model-risk-assessment-v1` schema. Local `Qwen3-1.7B` was found at runtime and passed one isolated schema probe in 46.851 seconds on CPU, returning the required `riskTypes`, `rawConfidence`, `complexity`, and `ambiguityFlags` fields. It was not enabled as the production router and was not used to fit the calibrator, so this report does not claim Qwen classification quality.

## Raw Confidence

On the 70-case calibration validation split:

- Risk precision: 0.8462
- Risk recall: 1.0000
- Risk F1: 0.9167
- Raw ECE: 0.1160
- Raw Brier: 0.1349

The router currently emits a small number of discrete confidence values. This limits calibration resolution.

## Calibration Method

Platt scaling and isotonic regression were fitted only on the 170-case calibration partition and compared on the 70-case validation partition. Isotonic regression was selected as `confidence-calibrator-v1` because validation ECE was 0.0000 and Brier was 0.1200, versus Platt ECE 0.1459 and Brier 0.1413.

The perfect in-template validation ECE is not treated as production evidence; it reflects repeated controlled templates and discrete confidence values.

## ECE / Brier

| Evaluation | Raw ECE | Calibrated ECE | Raw Brier | Calibrated Brier |
| --- | ---: | ---: | ---: | ---: |
| Calibration validation | 0.1160 | 0.0000 | 0.1349 | 0.1200 |
| Frozen holdout | 0.1902 | 0.2167 | 0.2734 | 0.3367 |

Calibration did not generalize to the frozen holdout. No parameters were changed after viewing holdout results.

## Risk Classification

Calibration validation Risk F1 is 0.9167. The unchanged frozen workflow Risk F1 is 0.7677.

## Severity Classification

| Metric | Calibration validation | Frozen holdout |
| --- | ---: | ---: |
| Accuracy | 1.0000 | 0.8167 |
| Macro F1 | 1.0000 | 0.8225 |
| HIGH severity undercall count | 0 | 4 |

Validation severity is derived from the same deterministic registry used for labels, so the frozen holdout is the more informative result.

## High-risk False Negatives

The original frozen governance safety metric remains `HIGH_RISK_AUTO_PASS_COUNT=0`. Severity evaluation nevertheless found four HIGH/CRITICAL to LOW/MEDIUM undercalls; these do not alter current Safety Gate or Human Review decisions.

## High-confidence Errors

Calibration validation has zero errors at calibrated confidence >=0.8. Frozen holdout has 26, caused mainly by isotonic mapping of the router's coarse 0.84/0.88 confidence values to 1.0 despite distribution shift. This is the primary blocker for production routing.

## Escalation Simulation

This is selection-only simulation and assumes no downstream model correctness. Threshold 0.7 is the calibration-set candidate: 70% escalation, 100% high-risk candidate escalation, and 0% low-severity false escalation on the controlled validation split. It must not be activated because frozen confidence calibration failed.

## Routing Matrix Candidate

| Severity | High confidence | Low confidence |
| --- | --- | --- |
| LOW | LOCAL_OK | ESCALATE_FLASH |
| MEDIUM | LOCAL_OR_FLASH | ESCALATE_FLASH |
| HIGH | STRICT_GOVERNANCE | ESCALATE_PRO_CANDIDATE |
| CRITICAL | HUMAN_REQUIRED_CANDIDATE | HUMAN_REQUIRED_CANDIDATE |

This matrix is documentation only. No DeepSeek/Qwen runtime router was added.

## Safety Gate Override

`SafetyGateTriggered=true` always prevents a `LOCAL_OK` recommendation. Unit tests verify the override to strict governance. The controlled validation split produced zero actual override events because its safety-triggered cases already had HIGH/CRITICAL severity; the invariant remains enforced.

## Frozen Holdout

- Frozen Gold SHA: `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`
- Cases with assessment: 120/120
- requested/actual mode: `hybrid/hybrid`; provider: `ready`; vectors: 71; dimension: 1024
- Hybrid Recall@1 / Recall@5: 0.9667 / 0.9667
- Risk F1: 0.7677
- Route / Decision / Reflection accuracy: 0.9417 / 0.8833 / 0.8083
- HIGH_RISK_AUTO_PASS_COUNT: 0
- API errors: 0

The original governance baseline is unchanged. The calibration holdout criterion failed because calibrated ECE and Brier regressed.

## Langfuse Integration

The Langfuse export contract now includes `riskSeverity`, `rawConfidence`, `calibratedConfidence`, `confidenceBucket`, `complexity`, `severityReasons`, and `escalationCandidate`. Numeric scores include `risk_severity_level`, `raw_confidence`, `calibrated_confidence`, and `escalation_candidate`. Fake-client integration tests verify the fields and redaction. Docker Desktop was unavailable during the final live trace delivery check, so a newly persisted ClickHouse trace was not claimed. A live API request still completed with Langfuse unavailable, confirming fail-open behavior and unchanged business decisions.

## Ablation

- A, risk type only: validation Risk F1 0.9167.
- B, risk type plus registry: deterministic, interpretable severity; frozen Macro F1 0.8225.
- C, raw confidence: frozen ECE 0.1902.
- D, calibrated confidence: frozen ECE 0.2167, a regression.

The severity registry adds interpretable value. The current calibrator does not add reliable holdout value.

## Limitations

- The database contains 54 usable human-reviewed outcomes, but only one is an independently recorded Tier A review action; the remaining 53 are historical AI-label acceptances.
- Controlled templates are less diverse than production language.
- Confidence outputs are coarse and self-reported by the current router path.
- Isotonic calibration overfit repeated confidence levels and did not transfer to frozen holdout.
- The one-case Qwen probe validates schema compatibility only, not quality or latency suitability.
- Final Langfuse persistence inspection remains pending because the local Docker engine was unavailable; export-contract tests passed.
- Four frozen severity undercalls and 26 high-confidence errors remain.

## Recommendation for Step21.3

Do not start a runtime Model Router. First collect a genuinely disjoint human-reviewed calibration set from Human Review, QA sampling, and shadow audits, then rerun calibration with grouped/source-aware validation and minimum bucket support. Preserve the frozen 120 cases as untouched holdout.

## Gate

`STEP21_2_SEVERITY_GATE = PASS_WITH_LIMITATIONS`

`STEP21_2_CALIBRATION_GATE = FAIL`

`STEP21_2_SAFETY_GATE = PASS`

`STEP21_2_HOLDOUT_GATE = FAIL`

`STEP21_2_REGRESSION_GATE = PASS`

`STEP21_2_GATE = FAIL`

## Step21.2 Failure Analysis

The Step 21.2 failure is frozen and retained. `confidence-calibrator-v1` was fitted primarily from controlled synthetic templates, while validation remained too close to those templates. Its isotonic mapping looked strong in-template but regressed on the untouched frozen holdout: ECE moved from `0.190167` to `0.216667`, and Brier from `0.273362` to `0.336667`. The artifact is preserved for reproducibility and marked `NOT_APPROVED_FOR_ROUTING`; its thresholds and values were not changed.

The frozen governance baseline remains unchanged. Step 21.2.1 did not modify the Router, Safety Gate, RAG, severity registry, thresholds, or frozen gold, and did not rerun the frozen workflow benchmark.

## Calibration Data Quality

Calibration provenance is now explicit:

| Tier | Meaning | Permitted use |
| --- | --- | --- |
| A | Independently human-reviewed gold | Fit and independent validation when coverage is sufficient |
| B | Human/QA-reviewed historical outcome | Fit or validation with source-aware controls |
| C | Shadow audit or production bad case awaiting confirmed gold | Annotation queue and analysis only |
| D | Controlled synthetic or weak label | Development, coverage stress, and diagnostics only |

`router_calibration_v2` contains no synthetic rows. It is versioned with source distribution, risk distribution, split policy, frozen hash, and its own content hash. Reviewer identity is neither queried nor exported; text is sanitized for email, phone number, identity number, and URL patterns before staging.

## Human Gold Coverage

- Current usable human-reviewed cases: `54 / 300` minimum.
- Tier A independent human gold: `1`.
- Tier B historical human-reviewed acceptances: `53`.
- Tier C/D rows used as gold: `0`.
- Risk coverage: all 54 usable rows are `after_sales_risk`.
- Source coverage: 53 `litemall_comment`, 1 `demo_review`.
- Source periods: 35 from `2026-06`, 18 from `2026-07`, 1 from `2026-09`.

This is insufficient in count, provenance strength, and taxonomy coverage. A sanitized annotation queue contains 116 unique non-frozen candidates: one explicit human override requiring a replacement gold label and 115 pending cases. The current 246-case numerical gap cannot be filled from unique available records; 130 additional independent cases still need to be collected.

## Source-aware Split

The provisional split groups by source type, source period, risk type, explicit/implicit expression, and merged near-duplicate template family. It produced 46 fit cases and 8 validation cases across 16 and 6 families respectively. The leakage audit reports:

- Normalized-text overlap between fit and validation: `0`.
- Template-family overlap between fit and validation: `0`.
- Exact overlap with frozen 120: `0`.
- Near-duplicate overlap with frozen 120: `0`.

The split is structurally valid but not statistically suitable for calibration because it contains only one risk type and too few independent Tier A labels.

## Confidence Cardinality

The current rule router emitted only two confidence values on the usable human set: `0.84` and `0.88`. The `0.84` bucket contains one case; the `0.88` bucket contains 53 cases. This cardinality is too low to justify treating `rawConfidence` as a continuous probability.

The historical Tier B labels also expose a semantic weakness: accepting a prior task outcome is not the same as independently confirming the router's full multi-label classification. The observed bucket accuracy must therefore be treated as diagnostic, not as a production probability estimate.

## Reliability Tier Analysis

Step 21.2.1 recommends ordinal reliability tiers instead of probability claims. On the current set, `VERY_HIGH` contains 53 cases and `HIGH` contains one; `MEDIUM` and `LOW` have no support. These names describe deterministic signal strength only and must not be presented as 90%, 80%, or any other probability.

Multi-signal analysis records current deterministic fields such as rule strength, multi-risk status, Safety Gate trigger, explicit expression, ambiguity, and severity. The available human set has no multi-risk, Safety Gate, or high-severity support, so no routing conclusion can be drawn from those slices yet.

## Error Taxonomy

The authoritative Step 21.2 frozen artifact records `HIGH_CONFIDENCE_ERROR_COUNT=26` and `HIGH_SEVERITY_UNDERCALL_COUNT=4`. The four undercalls are risk-type misses on `rating_manipulation-10`, `lexical_mismatch-03`, `lexical_mismatch-07`, and `lexical_mismatch-08`; no severity-registry or case-specific patch was applied.

The current checkpoint directory was subsequently reused by later executions. Reconstructing it now yields 38 high-confidence errors rather than the historical 26, so it is not valid evidence for a per-case taxonomy of the frozen run. The report preserves 26 as the authoritative aggregate and marks detailed classification `BLOCKED_HISTORICAL_PER_CASE_SNAPSHOT_UNAVAILABLE` instead of fabricating categories. Future frozen runs must persist immutable per-case assessment rows alongside aggregate metrics.

## Recalibration Result

Recalibration was deliberately not run. Raw, Platt, Isotonic, and optional Beta comparison remains `DEFERRED` until there are at least 300 sufficiently diverse human-reviewed cases and an independent source-aware validation split. A future candidate must improve ECE, not regress Brier, and not worsen high-risk error on independent validation before it may be labelled `CALIBRATOR_CANDIDATE`.

## Frozen Holdout

Frozen Gold SHA remains `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`. Step 21.2.1 reads the prior immutable aggregate only; it does not execute the 120-case holdout again and does not use holdout results for method, threshold, feature, or severity tuning.

## Router Readiness

`Qwen3-1.7B` remains offline-comparison-only because the measured CPU latency was about 46.851 seconds per sample. It is not a runtime router candidate. Langfuse availability is not required for this local deterministic data-governance result.

`STEP21_2_1_GATE = BLOCKED_ON_HUMAN_CALIBRATION_DATA`

Runtime Model Router work must not begin from this state.
