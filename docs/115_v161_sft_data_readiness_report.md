# v1.6.1 SFT Data Readiness Audit Report

## Conclusion

- Text SFT: `SFT_DATA_NOT_READY`
- VLM SFT: `VLM_SFT_DATA_NOT_READY`

## Blocking Reasons

- real_world dev requires at least 400 text samples; current=0
- real_world external test requires at least 200 text samples; current=0
- real multimodal external test requires at least 40 image-text samples; current=0

## Checks

| Check | Result |
| --- | --- |
| synthetic_review_count | 1200 |
| strict_query_count | 80 |
| real_dev_count | 0 |
| real_external_count | 0 |
| multimodal_external_count | 0 |
| source_manifest_count | 4 |
| synthetic_risk_type_distribution | {'normal_review': 180, 'negative_review': 300, 'after_sales_risk': 720} |
| privacy_hit_count | 0 |
| independent_final_test_available | False |

## Notes

This stage does not run QLoRA-SFT, DPO, or VLM fine-tuning. The current v1.6 synthetic data remains suitable for regression coverage and long-tail scenario checks, but real external text data, real multimodal data, dual-annotator agreement, privacy filtering, and license readiness are not complete. Therefore the project must not enter SFT.
