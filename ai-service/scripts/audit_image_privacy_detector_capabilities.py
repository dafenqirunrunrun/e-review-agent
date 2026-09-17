import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "real_world" / "audit" / "image_privacy_detector_capabilities.json"
DOC = ROOT / "docs" / "161_v16110_image_privacy_detector_capabilities.md"


def spec_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def detector(name, available, initialized, backend, version, test_pass, failure_code, failure_summary, mandatory, can_block=True):
    return {
        "detector_name": name,
        "available": bool(available),
        "initialized": bool(initialized),
        "model_or_backend": backend,
        "version": version,
        "test_input_pass": bool(test_pass),
        "failure_code": failure_code,
        "failure_summary": failure_summary,
        "mandatory": bool(mandatory),
        "can_block_clearance": bool(can_block),
    }


def get_version(module_name):
    try:
        module = __import__(module_name)
        return getattr(module, "__version__", "unknown")
    except Exception:
        return None


def main():
    pillow_available = spec_available("PIL")
    pillow_version = get_version("PIL") if pillow_available else None
    pii_regex_pass = bool(re.search(r"\b\d{3}[- ]?\d{3}[- ]?\d{4}\b", "call 555-123-4567"))

    detectors = [
        detector("pillow_file_read", pillow_available, pillow_available, "Pillow", pillow_version, pillow_available, None if pillow_available else "missing_dependency", None if pillow_available else "Pillow is unavailable.", True),
        detector("exif_read_remove", pillow_available, pillow_available, "Pillow EXIF", pillow_version, pillow_available, None if pillow_available else "missing_dependency", None if pillow_available else "EXIF inspection depends on Pillow.", True),
        detector("ocr_text_detection", spec_available("pytesseract") or spec_available("easyocr"), False, "pytesseract/easyocr", None, False, "missing_dependency", "No local OCR backend is initialized; online model download is forbidden.", True),
        detector("text_pii_regex", True, True, "python-re", None, pii_regex_pass, None, None, True),
        detector("qr_code_detection", spec_available("pyzbar"), False, "pyzbar", get_version("pyzbar") if spec_available("pyzbar") else None, False, "missing_dependency", "No QR decoder backend is available.", True),
        detector("barcode_detection", spec_available("pyzbar"), False, "pyzbar", get_version("pyzbar") if spec_available("pyzbar") else None, False, "missing_dependency", "No barcode decoder backend is available.", True),
        detector("face_detection", spec_available("cv2"), False, "opencv-haarcascade-or-dnn", get_version("cv2") if spec_available("cv2") else None, False, "missing_dependency", "No local face detector backend is available.", True),
        detector("license_plate_detection", spec_available("cv2"), False, "opencv-heuristic", get_version("cv2") if spec_available("cv2") else None, False, "missing_dependency", "License plate detection is an extension detector and is not initialized.", False, False),
        detector("screenshot_document_heuristic", True, True, "local-aspect-text-block-heuristic", "rule-v1", True, None, None, False, False),
        detector("waybill_candidate_heuristic", True, True, "local-keyword-layout-heuristic", "rule-v1", True, None, None, False, False),
        detector("image_duplicate_detection", True, True, "sha256-and-average-hash", "rule-v1", True, None, None, False, False),
        detector("qwen3_vl_privacy_hint", False, False, "Qwen3-VL auxiliary hint", None, False, "blocked_by_policy_gate", "Qwen3-VL cannot replace mandatory privacy detectors and is not used before clearance.", False, False),
    ]

    mandatory = [item for item in detectors if item["mandatory"]]
    mandatory_available = [item for item in mandatory if item["available"] and item["initialized"] and item["test_input_pass"]]
    missing = [item["detector_name"] for item in mandatory if not (item["available"] and item["initialized"] and item["test_input_pass"])]
    marker = "PRIVACY_DETECTOR_CAPABILITY_PASS" if not missing else "PRIVACY_DETECTOR_CAPABILITY_BLOCKED"

    report = {
        "marker": marker,
        "mandatory_detector_count": len(mandatory),
        "mandatory_available_count": len(mandatory_available),
        "missing_mandatory_detectors": missing,
        "detectors": detectors,
        "automated_clearance_allowed": not missing,
        "qwen3_vl_can_replace_mandatory_detectors": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rows = "\n".join(
        f"| {item['detector_name']} | {item['mandatory']} | {item['available']} | {item['initialized']} | {item['test_input_pass']} | {item['failure_code'] or ''} |"
        for item in detectors
    )
    DOC.write_text(
        "# V1.6.1.10 Image Privacy Detector Capability Audit\n\n"
        f"Status: `{marker}`\n\n"
        "This audit checks whether automatic image privacy clearance is technically allowed. "
        "It does not perform human review and does not download detector models online.\n\n"
        f"Mandatory detectors available: {len(mandatory_available)} / {len(mandatory)}\n\n"
        f"Missing mandatory detectors: {', '.join(missing) if missing else 'none'}\n\n"
        "| Detector | Mandatory | Available | Initialized | Test Pass | Failure |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        f"{rows}\n\n"
        "Conclusion: images must remain `automated_uncertain_detector_unavailable` until every mandatory detector is available and initialized.\n",
        encoding="utf-8",
    )
    print(marker)


if __name__ == "__main__":
    main()
