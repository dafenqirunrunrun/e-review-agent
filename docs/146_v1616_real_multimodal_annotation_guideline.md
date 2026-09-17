# v1.6.1.6 Real Multimodal Annotation Guideline

## Scope

This guideline applies to privacy-cleared real image-text review pairs only.
Raw images remain outside Git under `D:\EReviewAgent\data-private\realworld`.
Git stores only hashes, manifests, aggregate statistics, and audit outputs.

## Visual Fields

- `image_quality`
- `package_damage`
- `product_damage`
- `leakage`
- `contamination`
- `missing_part`
- `product_mismatch`
- `irrelevant_image`
- `privacy_risk`
- `visible_text`
- `visual_evidence_spans_or_regions`
- `text_image_consistency`
- `visual_uncertainty`

## Rules

Do not infer image content from review text, file names, source labels, or
expected answers. Blurred, occluded, or unrelated images should be marked as
`uncertain` or `irrelevant` instead of forcing a risk label. Package damage is
not the same as product damage. If privacy redaction removes the core visual
evidence, reject the sample for external-test use.

High-risk and text-image conflict samples should prioritize human review.
