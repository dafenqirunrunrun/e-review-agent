# Step 21.2.2A Demo Evaluation Dataset Construction

## Dataset Goal

Build two small, reproducible candidate datasets for the personal Demo without touching the existing frozen 120, running calibration, or treating weak/external labels as human gold.

## Public Sources

Three public sources contribute 125 of 180 cases: ASAP contributes 65, the Figshare Chinese e-commerce negative-review dataset contributes 35, and the pinned Hugging Face fake-review subset contributes 25. Public data supplies normal language, legitimate complaints, hard negatives, and fake/genuine contrast. E-Review-specific design is reserved for governance boundaries that public labels do not express reliably.

## License

ASAP and the selected Hugging Face dataset declare Apache-2.0. Figshare reports CC BY 4.0 through its public article API. Amazon Reviews 2023 is recorded as `SKIPPED_LICENSE_UNCLEAR`, with zero selected text. Selected-source license checks pass.

## Calibration 120 Composition

- Public/open: 90 cases; ASAP 50, Figshare 25, Hugging Face 15.
- E-Review expert-designed: 30 cases.
- Difficulty: 38 easy, 56 medium, 26 hard.
- Expression: 38 explicit, 72 implicit, 10 mixed.
- Status: every row is `CANDIDATE_ONLY`; none is approved for calibration.

## Boundary 60 Composition

- Public/open: 35 cases; ASAP 15, Figshare 10, Hugging Face 10.
- E-Review expert-designed: 25 cases.
- `implicit_or_paraphrase`: 15.
- `lexical_mismatch`: 10.
- `hard_negative`: 15.
- `multi_risk_or_conflict`: 10.
- `ambiguous_context`: 5.
- `noisy_or_adversarial`: 5.

## Chinese Native / Translated

Across both sets, 155 cases are native Chinese and 25 are translations of already-selected English rows. Sampling happened before translation. Translation changes language only; no translation adds cashback, five-star, refund, or other E-Review risk semantics.

## E-Review Specific Cases

There are 55 project-specific candidates: 30 in Calibration and 25 in Boundary. They cover paid-review incentives, score manipulation, review suppression, after-sales versus manipulation, multi-risk combinations, implicit phrasing, and noisy obfuscation. They are labelled `expert_designed`, not `human_gold`.

The 54 Step 21.2.1 historical cases were not copied into this set: they cover only `after_sales_risk`, and part of the historical export has unusable encoding artifacts. This avoids converting weak or corrupted history into apparent diversity.

## Risk Coverage

Calibration risk counts are: `normal_review=40`, `negative_review=25`, `after_sales_risk=20`, `fake_review=10`, `paid_review=9`, `rating_manipulation=11`, `review_suppression=8`, `safety_or_fraud_risk=5`, and `harassment_or_abuse=2`. Multi-label cases contribute to more than one count.

All core registered risks required for this demo are represented. `incentivized_review` is not used as a risk type because it is an evidence tag, not a code in the real registry.

## Boundary Coverage

Boundary distribution matches the requested 15/10/15/10/5/5 structure exactly. It includes 14 multi-risk rows and 5 explicitly ambiguous rows. All 60 rows are marked hard because this set is intentionally a challenge set.

## Frozen Isolation

- Frozen case count: 120.
- Frozen SHA-256: `9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54`.
- Exact overlap: 0.
- Normalized overlap: 0.
- Near overlap: 0.
- Template-family overlap: 0.

The frozen file was read only for isolation checks. It was not copied, modified, sampled, evaluated, or used for label decisions.

## Template Diversity

The 180 cases have 180 normalized texts and 180 template families. Pairwise near-duplicate count is zero at the frozen deterministic threshold. Numeric substitutions such as changing only cashback amounts therefore cannot inflate coverage.

## Deterministic Completeness Score

Score: `70 / 70`.

Risk type coverage 15, severity coverage 10, explicit/implicit coverage 10, hard-negative coverage 10, multi-risk coverage 5, source diversity 10, template diversity 5, and frozen isolation 5. This score measures structural completeness only and is not a model-quality score.

## AI Usage

- Translation calls represented in the curated cache: 25.
- E-Review boundary cases assisted: 25.
- E-Review calibration business cases assisted: 30.
- Runtime model/API calls during deterministic rebuild: 0.
- LLM-as-a-Judge calls: 0.

Token counts were unavailable and are recorded as null rather than estimated. Rebuilds reuse the checked-in translation and business-case definitions.

## Current Limitations

- Calibration rows remain candidates, not human-reviewed gold.
- `paid_review` has 9 Calibration examples, below the suggested 15, because no sufficiently clear Chinese public incentive-labelled dataset was approved.
- ASAP is restaurant/O2O language rather than product-review governance data.
- External fake-review labels describe deceptive/computer-generated reviews, not proof of paid incentives or score manipulation.
- Figshare label mappings are candidate mappings, not adjudicated E-Review labels.
- No large external robustness set is created in this stage.

## Next Step

Step 21.2.2B may perform the separately requested manual multi-prompt review. This stage does not run LLM judges, calibration, reliability thresholds, frozen model evaluation, Model Router, or Qwen/Flash/Pro comparison.

## Gate

All required deterministic gates pass. Because paid-review source coverage remains below the suggested target:

`STEP21_2_2A_GATE = PASS_WITH_COVERAGE_LIMITATION`
