import importlib.util
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "ai-service" / "tests" / "fixtures" / "privacy-detectors"
OUT = ROOT / "data" / "real_world" / "audit" / "privacy_detector_self_test.json"
DOC = ROOT / "docs" / "164_v16111_privacy_detector_self_test.md"


def has_module(name):
    return importlib.util.find_spec(name) is not None


def status(pass_condition, partial_condition=False):
    if pass_condition:
        return "capability_pass"
    if partial_condition:
        return "capability_partial"
    return "capability_blocked"


def main():
    fixtures_present = all((FIXTURE_DIR / name).exists() for name in [
        "clean_product_like.png",
        "phone_text.png",
        "email_text.png",
        "shipping_label.png",
        "qr_code.png",
        "barcode.png",
    ])
    pil_ok = has_module("PIL") and fixtures_present
    pii_phone = bool(re.search(r"\b\d{3}[- ]?\d{3}[- ]?\d{4}\b", "Phone: 555-123-4567"))
    pii_email = bool(re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "Email: test.person@example.test"))
    pii_negative = not bool(re.search(r"\b\d{3}[- ]?\d{3}[- ]?\d{4}\b", "clean product package"))
    ocr_backend = "tesseract+pytesseract" if has_module("pytesseract") and shutil.which("tesseract") else (
        "rapidocr_onnxruntime" if has_module("rapidocr_onnxruntime") and has_module("onnxruntime") else None
    )
    qr_backend = "zxingcpp" if has_module("zxingcpp") else None
    barcode_backend = "zxingcpp" if has_module("zxingcpp") else None
    face_backend = None
    face_partial = False
    if has_module("cv2"):
        try:
            import cv2
            if getattr(getattr(cv2, "data", None), "haarcascades", None):
                face_backend = "opencv_haar_cascade"
                face_partial = True
        except Exception:
            face_backend = None

    tests = {
        "pillow_file_integrity": {
            "backend": "Pillow",
            "positive_result": pil_ok,
            "negative_result": True,
            "status": status(pil_ok),
        },
        "pii_regex": {
            "backend": "python_re",
            "positive_result": pii_phone and pii_email,
            "negative_result": pii_negative,
            "status": status(pii_phone and pii_email and pii_negative),
        },
        "ocr_text_detection": {
            "backend": ocr_backend or "none",
            "positive_result": False,
            "negative_result": None,
            "status": status(False),
            "blocked_reason": "no_local_ocr_backend_initialized" if not ocr_backend else "ocr_backend_present_but_positive_fixture_not_executed",
        },
        "qr_code_detection": {
            "backend": qr_backend or "none",
            "positive_result": False,
            "negative_result": None,
            "status": status(False),
            "blocked_reason": "no_local_qr_backend_initialized" if not qr_backend else "qr_backend_present_but_positive_fixture_not_executed",
        },
        "barcode_detection": {
            "backend": barcode_backend or "none",
            "positive_result": False,
            "negative_result": None,
            "status": status(False),
            "blocked_reason": "no_local_barcode_backend_initialized" if not barcode_backend else "barcode_backend_present_but_positive_fixture_not_executed",
        },
        "face_detection": {
            "backend": face_backend or "none",
            "positive_result": False,
            "negative_result": None,
            "status": status(False, face_partial),
            "blocked_reason": "backend_initialized_but_positive_fixture_unavailable" if face_partial else "no_local_face_backend_initialized",
        },
    }
    mandatory = ["ocr_text_detection", "qr_code_detection", "barcode_detection", "face_detection"]
    mandatory_pass = all(tests[name]["status"] == "capability_pass" for name in mandatory)
    any_partial = any(item["status"] == "capability_partial" for item in tests.values())
    marker = "PRIVACY_DETECTOR_CAPABILITY_PASS" if mandatory_pass else (
        "PRIVACY_DETECTOR_CAPABILITY_PARTIAL" if any_partial else "PRIVACY_DETECTOR_CAPABILITY_BLOCKED"
    )
    report = {
        "marker": marker,
        "fixtures_present": fixtures_present,
        "synthetic_fixtures_counted_as_real_pilot": False,
        "detectors": tests,
        "mandatory_capability_pass": mandatory_pass,
        "qwen3_vl_replaces_mandatory_detectors": False,
        "ocr_full_text_in_git_report": False,
        "qr_full_content_in_git_report": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = "\n".join(f"| {name} | {item['backend']} | {item['status']} | {item.get('blocked_reason', '')} |" for name, item in tests.items())
    DOC.write_text(
        "# V1.6.1.11 Privacy Detector Self Test\n\n"
        f"Status: `{marker}`\n\n"
        "Synthetic fixtures are used only for detector unit tests and are not counted as real pilot images.\n\n"
        "| Detector | Backend | Status | Reason |\n| --- | --- | --- | --- |\n"
        f"{rows}\n\n"
        "Automatic private-pilot low-risk classification remains blocked unless OCR, QR, barcode, and face detectors all pass positive and negative fixtures.\n",
        encoding="utf-8",
    )
    print(marker)


if __name__ == "__main__":
    main()
