# v1.6.1 VLM Visual Evidence Evaluation Report

## Conclusion

`MULTIMODAL_VLM_EVAL_BLOCKED`

- External multimodal count: `0`
- Required external multimodal count: `40`
- Model available: `False`
- Model directory kind: `repo_external_configured_path`

## Required Metrics

- `visual_schema_valid_rate`: not executed
- `visual_field_complete_rate`: not executed
- `image_quality_accuracy`: not executed
- `ocr_exact_match`: not executed
- `ocr_character_f1`: not executed
- `package_damage_f1`: not executed
- `product_damage_f1`: not executed
- `leakage_f1`: not executed
- `missing_part_f1`: not executed
- `product_mismatch_f1`: not executed
- `irrelevant_image_f1`: not executed
- `text_image_consistency_macro_f1`: not executed
- `visual_evidence_support_rate`: not executed
- `visual_unsupported_claim_rate`: not executed
- `privacy_risk_recall`: not executed
- `fallback_rate`: not executed
- `avg_latency_ms`: not executed
- `p95_latency_ms`: not executed
- `gpu_peak_memory_mb`: not executed

## Blocking Reasons

- real multimodal external test set requires at least 40 samples; current=0
- local Qwen3-VL/Qwen2.5-VL config, processor/tokenizer, and weights are not available outside Git

## Evidence Boundary

This report evaluates the independent VLM visual-evidence extraction path. It
does not report visual evidence support, unsupported visual claim rate, OCR, or
image-quality metrics while real external multimodal samples and local VLM
weights are unavailable.
