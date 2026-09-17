# Step 21.2.2C Dataset Semantic Gate

## Rejudge Method

The current Codex instance reviewed only the existing rejudge queue: 81 semantic cases and 41 Boundary cases. This is a single-judge review, not independent multi-model agreement and not human adjudication. Results contain structured verdicts and short reason codes only; no chain-of-thought is stored.

Existing labels were treated as candidates. The review did not run a GPT API, modify Frozen Gold, execute a model benchmark, or tune the Dataset to a target pass rate.

## Calibration Results

Calibration final quality is 96 PASS, 23 FAIL, and 1 UNCERTAIN out of 120, for a pass rate of 80.00%. This is below the 90% Demo threshold.

The remaining failures are concentrated in weak external mappings: restaurant complaints omit explicit safety or harassment semantics, some free-experience reviews are labelled normal, Figshare mappings confuse general negative, after-sales, and fraud risks, and three translated deceptive-review labels are not inferable from the Chinese text alone.

## Boundary Results

Boundary validity is 54 PASS, 6 FAIL, and 0 UNCERTAIN out of 60, for a pass rate of 90.00%. This passes the 85% validity threshold.

Challenge distribution is 37 HIGH, 13 MEDIUM, and 10 LOW. HIGH plus MEDIUM is 83.33%, passing the 80% challenge threshold. Three retained external complaints are not real hard negatives; three candidate boundaries omit a paid-review risk that is explicit in their incentive condition.

## Abstention Results

All five abstention cases are valid: 5 CORRECT, 0 INCORRECT, and 0 UNCERTAIN. Abstention accuracy is 100%. They remain excluded from ordinary risk precision, recall, F1, and accuracy.

## Multi-risk Results

The single-judge review finds 13 `MISSED_MULTI_RISK` cases. Repeated patterns include paid review plus rating manipulation, suppression plus after-sales pressure, harassment plus suppression or complaint context, and fake review plus safety/manipulation signals. Since the same omission pattern occurs at least three times, the error is systematic under the declared Gate definition.

## Keyword Shortcut

Twenty-two of 60 Boundary cases have `keywordShortcutRisk=true`, a ratio of 36.67%. This exceeds the maximum 25% threshold. The verdict was not changed to force the ratio down.

## Chinese Quality

Natural Chinese count is 177 of 180, or 98.33%, passing the 95% threshold. The three failures contain escaped line artifacts or a long copied introduction mixed with a short review.

## Remaining Limitations

- `SINGLE_JUDGE_LIMITATION`: the review is by the current Codex instance only.
- Calibration semantic pass rate remains below threshold.
- Boundary keyword shortcut risk remains above threshold.
- Missed multi-risk errors remain systematic.
- Boundary source diversity remains limited after low-quality external Boundary rows were removed.
- No candidate is human gold or multi-model validated.

## Demo Readiness

The Dataset is not frozen as Demo-ready. A final minimal repair was not performed because more than five semantic defects remain; applying a five-case patch could not resolve the failed Calibration and multi-risk gates. The existing v2.1 candidate files remain unchanged.

## Final Gate

`DATASET_SEMANTIC_GATE = FAIL`

`STEP21_2_2C_GATE = FAIL`

The failure is an explicit quality result, not a runtime error. Confidence calibration, Model Router, model comparison, and Frozen model evaluation have not started.

## Final Bounded Repair

Step 21.2.2D performs the final and only bounded repair iteration. It changes 23 cases against a hard maximum of 30: 12 Calibration cases and 11 Boundary cases. Thirteen missed multi-risk cases are repaired using short evidence-span summaries, and every changed label is passed through the existing `RiskSeverityEvaluator`.

The Calibration repair addresses ten explicit multi-risk omissions plus one clear negative-review mapping and one polluted copied-introduction case. Boundary repair corrects three missing paid-review labels, removes one false multi-risk label, replaces three low-value ordinary complaints with relational hard negatives, and rewrites four additional shortcut-prone cases. The three previously unnatural Chinese cases are cleaned within the same repair set. The five Abstention cases are unchanged.

Calibration improves from 96/23/1 to 108 PASS, 11 FAIL, and 1 UNCERTAIN, reaching 90.00%. Boundary improves from 54/6/0 to 60 PASS, 0 FAIL, and 0 UNCERTAIN. Challenge distribution is 40 HIGH, 13 MEDIUM, and 7 LOW; HIGH plus MEDIUM is 88.33%.

Keyword shortcut falls from 22/60 (36.67%) to 15/60 (25.00%). `MISSED_MULTI_RISK` falls from 13 to 0. Natural Chinese improves from 177/180 to 180/180. Abstention remains 5/5 correct.

Final dataset hashes:

- Calibration: `DB3B4B9692EBB08B1A4A0CC45715084369AEE4BD571BCBAED6FDBF297F6A48A3`
- Boundary: `5472C19987A23F57BF121321D47958C1D5ED0344615E12C9714CD26A4A021730`
- Frozen Gold: `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`

The final status is `SEMANTICALLY_ACCEPTED_FOR_DEMO`. Calibration remains a `SEMANTICALLY_REVIEWED_CANDIDATE`, not human gold and not evidence of production probability calibration.

`DATASET_SEMANTIC_GATE = PASS_WITH_SINGLE_JUDGE_LIMITATION`

`STEP21_2_2D_GATE = PASS_WITH_SINGLE_JUDGE_LIMITATION`
