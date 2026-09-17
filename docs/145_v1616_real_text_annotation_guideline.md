# v1.6.1.6 Real Text Annotation Guideline

## Scope

This guideline applies only to compliant real-world text reviews that have
passed source-license audit, privacy redaction, deduplication, and split
isolation. Synthetic reviews remain useful for regression and long-tail
coverage, but must not be described as real external-test data.

## Required Fields

- `primary_risk_type`
- `secondary_risk_types`
- `risk_level`
- `need_human_review`
- `text_evidence_spans`
- `expected_action`
- `ambiguity_flag`
- `annotator_confidence`
- `annotation_note`

## Rules

Evidence must come from the review text itself. Emotional language does not
automatically imply high risk. Refund requests should be treated as customer
intent, not as an automatic refund decision. When evidence is insufficient,
mark the sample as ambiguous and route to human review.

External-test labels must never be used for RAG indexing, prompt selection,
route-threshold tuning, SFT, DPO, or any model-training workflow.
