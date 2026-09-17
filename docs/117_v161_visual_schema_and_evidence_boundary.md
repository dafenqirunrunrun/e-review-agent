# v1.6.1 Visual Schema and Evidence Boundary

## Purpose

This document defines the structured visual-evidence output boundary for the
VLM path. Qwen3-VL or an equivalent local VLM may extract visual evidence from
the current review images, but it must not replace the final governance decision
made by the text governance model and routing policy.

## Required Schema

VLM output must conform to `VisualEvidenceResult`:

- `image_available`
- `image_quality`
- `ocr_text`
- `visual_findings`
- `package_damage_detected`
- `product_damage_detected`
- `leakage_detected`
- `missing_part_detected`
- `product_mismatch_detected`
- `privacy_risk_detected`
- `text_image_consistency`
- `visual_risk_level`
- `visual_evidence`
- `unsupported_visual_claims`
- `need_human_review`
- `missing_information`

`visual_findings[*].confidence` must stay within `[0, 1]`. Schema validation
failure must trigger repair or human review. It must not be silently accepted.

## Evidence Separation

| Evidence type | Source | Forbidden use |
| --- | --- | --- |
| `text_evidence` | Current review text | Must not be inferred from image labels or retrieved cases |
| `visual_evidence` | Visible content in current images | Must not come from review text, image filenames, paths, or manual labels |
| `retrieved_case_evidence` | Historical cases from Hybrid RAG | Must not be written as a fact about the current image |

The three evidence streams must remain separated until the final governance
decision step. A retrieved case may provide precedent, but it cannot prove what
is visible in the current image.

## Visual Evidence Rules

1. If the image is unclear, occluded, low resolution, or irrelevant, output
   `uncertain` and route to human review.
2. Packaging damage alone must not be written as product damage unless the
   product itself is visibly damaged.
3. Claims not supported by the image must be omitted or recorded in
   `unsupported_visual_claims`.
4. Privacy findings such as faces, phone numbers, addresses, shipping labels, or
   order numbers must set `privacy_risk_detected=true`.
5. Full sensitive OCR text must not be persisted; only redacted summaries are
   allowed.
6. The VLM must not decide refunds, compensation, bans, penalties, or final
   merchant actions.
7. If VLM execution fails, `need_human_review=true` and
   `missing_information` must contain the visual-analysis failure reason.

## Current Verification

Automated tests currently cover:

- invalid confidence values are rejected by schema validation;
- uncertain or blurred images require human review;
- missing local VLM weights produce a blocked smoke result;
- uncertain text-image consistency routes to human review.

Current independent visual evaluation status:

- Result file: `data/multimodal/eval/vlm_visual_eval_results.json`
- Report: `docs/128_v161_vlm_visual_evidence_eval_report.md`
- Marker: `MULTIMODAL_VLM_EVAL_BLOCKED`

The blocked status is expected because the local VLM weights and isolated real
multimodal external test set are not available.
