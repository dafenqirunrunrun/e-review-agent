# V1.6.1.10 Image Privacy Detector Capability Audit

Status: `PRIVACY_DETECTOR_CAPABILITY_BLOCKED`

This audit checks whether automatic image privacy clearance is technically allowed. It does not perform human review and does not download detector models online.

Mandatory detectors available: 3 / 7

Missing mandatory detectors: ocr_text_detection, qr_code_detection, barcode_detection, face_detection

| Detector | Mandatory | Available | Initialized | Test Pass | Failure |
| --- | --- | --- | --- | --- | --- |
| pillow_file_read | True | True | True | True |  |
| exif_read_remove | True | True | True | True |  |
| ocr_text_detection | True | False | False | False | missing_dependency |
| text_pii_regex | True | True | True | True |  |
| qr_code_detection | True | False | False | False | missing_dependency |
| barcode_detection | True | False | False | False | missing_dependency |
| face_detection | True | False | False | False | missing_dependency |
| license_plate_detection | False | False | False | False | missing_dependency |
| screenshot_document_heuristic | False | True | True | True |  |
| waybill_candidate_heuristic | False | True | True | True |  |
| image_duplicate_detection | False | True | True | True |  |
| qwen3_vl_privacy_hint | False | False | False | False | blocked_by_policy_gate |

Conclusion: images must remain `automated_uncertain_detector_unavailable` until every mandatory detector is available and initialized.
