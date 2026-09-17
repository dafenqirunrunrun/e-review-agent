# Step 21.2.2B Dataset v2 Repair

## Judge Aggregation

Judge A covers all 180 v1 cases: 114 PASS, 60 FAIL, and 6 UNCERTAIN. Judge B covers all 60 v1 Boundary cases: 24 PASS and 36 FAIL. The combined table is stored in `judge_aggregation_v1.jsonl`; suggestions remain proposed repair evidence and are never promoted to human gold.

The Boundary cross-matrix is: 20 A-PASS/B-PASS, 14 A-PASS/B-FAIL, 3 A-FAIL/B-PASS, 21 A-FAIL/B-FAIL, 1 A-UNCERTAIN/B-PASS, and 1 A-UNCERTAIN/B-FAIL.

## Calibration Repair

Calibration v2 remains 120 cases. Judge-A-passed rows are retained. Five translated rows with explicit translation-drift findings are removed and replaced by native Chinese rows whose labels passed Judge A but whose Boundary value failed Judge B. Clear missed multi-risk findings on project-authored cases are recorded as proposed repairs; external mapping conflicts remain `NEEDS_ADJUDICATION` rather than being accepted in bulk.

All Calibration rows remain `CANDIDATE_ONLY`. v2 adds `labelStatus`, `judgeConsensusStatus`, proposed labels, and repair action provenance.

## Boundary Repair

Boundary v2 remains 60 cases. It retains the 24 rows accepted by Judge B, including three valuable label/boundary disagreements for rejudge, and replaces all 36 Judge-B-failed rows. The replacements emphasize negation, quoted speech, conditional relations, indirect phrasing, counter-signals, ambiguity, and noisy expression.

The requested distribution remains 15 implicit/paraphrase, 10 lexical mismatch, 15 hard negative, 10 multi-risk/conflict, 5 ambiguous context, and 5 noisy/adversarial. Distribution was retained only after deterministic checks found no duplicate or frozen overlap.

## Source Quality Analysis

ASAP and translated HF rows were removed from the Boundary core because Judge B passed none of them. Three Figshare hard negatives remain because Judge B accepted their challenge value. Twenty-one original E-Review cases remain, and 36 new candidate replacements await independent rejudge.

This produces 57 project-specific and 3 external Boundary cases, outside the approximate v2 source target. It is an explicit quality-first decision based on observed Judge B results, not a claim that source diversity is solved.

## Translation Drift

Five Calibration translations explicitly flagged for drift are replaced with native Chinese cases. Boundary translations failed Judge B and are replaced as part of the 36-row Boundary repair. No bulk retranslation or external model call is performed. A literal escaped newline and one HTML ellipsis entity in retained public rows are normalized and queued for recheck.

## Multi-risk Repair

The repair policy accepts no Judge label blindly. Only project-authored cases with a `MISSED_MULTI_RISK` finding and valid registry codes receive a proposed multi-risk change. External-source conflicts retain their current candidate label plus the Judge proposal and require adjudication.

## Severity Repair

Every v2 severity is recomputed with `RiskSeverityEvaluator` and `risk-severity-registry-v1`. The maximum registered risk severity and existing context modifiers determine the result. Emotional tone and a Judge's isolated severity suggestion do not override the project rule.

## Benchmark Scope

`text_router_benchmark_scope_v1.json` classifies all 15 registered codes. Ten business classes are in scope for text routing. `rating_conflict` and `modality_conflict` require additional inputs; `low_confidence` is runtime state; `fake_review_suspected` is an evidence-strength intermediate state; and `other` is a fallback. Rare in-scope classes remain qualitative slices and are not assigned stable per-class F1 claims.

## Dataset v2 Distribution

The manifest records all source, risk, severity, expression, difficulty, boundary, label-status, and consensus distributions. Calibration count is 120 and Boundary count is 60. There are 180 template families, with zero exact, normalized, or near duplicates.

The deterministic keyword estimate reports four counter-signal cases containing common trigger words without a corresponding strong governance label. This estimate is diagnostic only and is not a model benchmark.

## Frozen Isolation

Frozen Gold remains read-only with 120 cases and SHA-256 `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`. Exact, near, and template-family overlap with v2 are all zero. Only aggregate risk, route, decision, language, and multi-risk distributions are recorded; no frozen case drives a v2 repair.

## Rejudge Queue

The queue contains 81 unique cases: changed labels or severity, uncertainty/disagreement, text normalization, and all new Boundary replacements. This exceeds the anticipated 20-50 because the supplied audits identify 60 label failures and 36 Boundary failures; reducing the queue would hide unresolved cases.

Judge A recheck is split into five batches and Judge B Boundary recheck into three batches, each with no more than 20 items. Batch payloads omit old verdicts to reduce anchoring bias. No GPT API is called automatically.

## Remaining Limitations

- `DATASET_SEMANTIC_GATE` remains `PENDING_INDEPENDENT_REJUDGE`.
- Boundary source diversity is intentionally low after all ASAP and HF Boundary rows failed Judge B.
- External-source label conflicts still require human or independent rejudge adjudication.
- The rejudge queue is larger than estimated because unresolved audit findings were not discarded.
- Judge C's source file contains damaged Chinese text in narrative fields, so findings are tracked by the explicitly stated categories and source file hash rather than copied verbatim.
- No calibration, Model Router, model comparison, or Frozen model evaluation has started.

## Scope Consistency Patch

Step 21.2.2B.1 found five `ambiguous_context` rows whose classification labels used out-of-scope state codes: four `low_confidence` and one `fake_review_suspected`. Their text, case count, and Boundary type are unchanged. Their former codes are retained only in `provenanceRiskTypes`.

The five rows now use `riskTypes=[]`, `benchmarkRiskTypes=[]`, `evaluationTarget=ABSTENTION`, `expectedDisposition=ESCALATE_OR_ABSTAIN`, and `excludeFromRiskTypeMetrics=true`. They are excluded from ordinary risk precision, recall, F1, and accuracy. They are evaluated separately with abstention accuracy, escalation accuracy, and false-confident-classification count.

All other rows default to `RISK_CLASSIFICATION` when `evaluationTarget` is absent, keeping this a minimal patch and preserving the Calibration v2 hash. The scope registry now gives every risk code an explicit `benchmarkRole`. Rejudge batches include the abstention contract but no previous verdict or repair suggestion.

The patch does not change text, Calibration/Boundary counts, Frozen Gold, or run a Judge. Dataset revision is `v2.1`. The artifact SHA-256 values are:

- Calibration: `ACA742F60498B16C2757F4AF5CD91DAEC6522C0B4954D0CF9ADDC682FDC75CEC` (unchanged)
- Boundary: `37AB16979D8B93CF40939F718D3ACD2EF527DBBBBD55AE6DF0AC9088E9B8D0DD`
- Manifest: `71472BA73B5123FEB0574DC8BD4A5F27464FA06FD8AFCED9F86C5FF904315613`
- Rejudge queue: `5BD54AA25DB7E03D1032770795BA68D583FC03ED89554BB0C8239BA4C7E7D5F2`

`DATASET_SEMANTIC_GATE` remains `PENDING_INDEPENDENT_REJUDGE`.
