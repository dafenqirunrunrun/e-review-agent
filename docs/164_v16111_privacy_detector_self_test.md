# V1.6.1.11 Privacy Detector Self Test

Status: `PRIVACY_DETECTOR_CAPABILITY_BLOCKED`

Synthetic fixtures are used only for detector unit tests and are not counted as real pilot images.

| Detector | Backend | Status | Reason |
| --- | --- | --- | --- |
| pillow_file_integrity | Pillow | capability_pass |  |
| pii_regex | python_re | capability_pass |  |
| ocr_text_detection | none | capability_blocked | no_local_ocr_backend_initialized |
| qr_code_detection | none | capability_blocked | no_local_qr_backend_initialized |
| barcode_detection | none | capability_blocked | no_local_barcode_backend_initialized |
| face_detection | none | capability_blocked | no_local_face_backend_initialized |

Automatic private-pilot low-risk classification remains blocked unless OCR, QR, barcode, and face detectors all pass positive and negative fixtures.
