# v1.6.1 Final Status Summary

## Conclusion

- Marker: `V161_FINAL_STATUS_SUMMARY_COMPLETE`
- Final gate marker: `V161_FINAL_GATE_BLOCKED`
- Release allowed: `False`

This report maps the requested 42 final-output fields to current machine-readable evidence. `BLOCKED`, `null`, and `not_available` values are preserved when real data, local VLM weights, or real inference evidence is missing.

## 42-Item Summary

| ID | Field | Current value |
| --- | --- | --- |
| 1 | branch | `audit/v1.6.1-realworld-multimodal` |
| 2 | compliant_real_text_data_found | `False` |
| 3 | compliant_real_multimodal_data_found | `False` |
| 4 | data_sources_and_licenses | `[{"source_id": "banglishrev_hf_2024", "source_name": "BanglishRev: Bangla-English and Code-mixed E-commerce Review Dataset", "license": "cc-by-nc-sa-4.0", "status": "candidate_allowed_for_research_after_privacy_filtering", "contains_images": true, "redistribution_allowed": true}, {"source_id": "amazon_reviews_2023_mccauley", "source_name": "Amazon Reviews 2023", "license": "not_found_on_dataset_card_or_project_site", "status": "blocked_license_unclear", "contains_images": true, "redistribution_allowed": null}, {"source_id": "amazon_berkeley_objects_abo", "source_name": "Amazon Berkeley Objects Dataset", "license": "cc-by-4.0", "status": "image_reference_only_not_review_dataset", "contains_images": true, "redistribution_allowed": true}, {"source_id": "yelp_open_dataset", "source_name": "Yelp Open Dataset", "license": "educational_use_terms_not_open_redistribution_license", "status": "not_ecommerce_product_review_dataset", "contains_images": true, "redistribution_allowed": false}]` |
| 5 | real_text_count | `0` |
| 6 | real_multimodal_count | `0` |
| 7 | external_text_test_size | `0` |
| 8 | external_multimodal_test_size | `0` |
| 9 | raw_real_images_in_git | `no` |
| 10 | vlm_model_name | `Qwen3-VL-2B-Instruct` |
| 11 | vlm_4bit_enabled | `False` |
| 12 | actual_gpu_and_peak_memory | `cuda available via torchtest; VLM peak memory not_available because VLM inference is blocked` |
| 13 | vlm_avg_and_p95_latency | `{"avg_latency_ms": null, "p95_latency_ms": null}` |
| 14 | exact_duplicate_count | `0` |
| 15 | near_duplicate_count | `0` |
| 16 | original_synthetic_hit3_hit5 | `{"hit_at_3": 1.0, "hit_at_5": 1.0}` |
| 17 | strict_synthetic_hit3_hit5 | `{"hit_at_3": 0.2125, "hit_at_5": 0.325}` |
| 18 | real_external_no_oracle_hit3_hit5 | `BLOCKED: real external text test set is not available` |
| 19 | real_text_risk_type_macro_f1 | `null` |
| 20 | text_only_macro_f1 | `null` |
| 21 | image_only_macro_f1 | `null` |
| 22 | text_image_macro_f1 | `null` |
| 23 | text_image_rag_macro_f1 | `null` |
| 24 | visual_evidence_support_rate | `null` |
| 25 | visual_unsupported_claim_rate | `null` |
| 26 | text_image_consistency_macro_f1 | `null` |
| 27 | privacy_risk_recall | `null` |
| 28 | human_review_precision | `1.0` |
| 29 | human_review_recall | `1.0` |
| 30 | high_risk_review_recall | `1.0` |
| 31 | unsafe_auto_pass_rate | `0.0` |
| 32 | multimodal_vlm_eval_pass | `False` |
| 33 | realworld_multimodal_route_calibration_pass | `False` |
| 34 | sft_data_ready | `False` |
| 35 | vlm_sft_data_ready | `False` |
| 36 | python_test_result | `================== 62 passed, 1 skipped, 1 warning in 16.74s ==================` |
| 37 | maven_result | `see docs/123_v161_build_regression_report.md` |
| 38 | admin_h5_build_result | `see docs/123_v161_build_regression_report.md` |
| 39 | commit | `generated_from_commit=090cc3c2; final artifact commit is assigned after this report is committed` |
| 40 | tag | `none` |
| 41 | working_tree_clean_at_generation | `no; summary generation observed uncommitted files` |
| 42 | recommend_enter_qwen3_ms_swift_qlora_sft | `no; SFT_DATA_READY and VLM_SFT_DATA_READY are both false` |

## Notes

- Blocked or null values are not failures of this summary script; they are the current verified state.
- Do not create `v1.6.1-realworld-multimodal-evaluation` unless the final gate reports `V161_FINAL_GATE_PASS`.
