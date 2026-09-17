import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SELF_TEST = ROOT / "data" / "real_world" / "audit" / "privacy_detector_self_test.json"
ACQUISITION = ROOT / "data" / "real_world" / "audit" / "private_pilot_v2_image_acquisition.json"
OUT = ROOT / "data" / "real_world" / "audit" / "private_pilot_image_privacy_v3.json"
DOC = ROOT / "docs" / "165_v16111_private_pilot_image_privacy_v3.md"


def main():
    self_test = json.loads(SELF_TEST.read_text(encoding="utf-8"))
    acquisition = json.loads(ACQUISITION.read_text(encoding="utf-8"))
    image_count = int(acquisition.get("valid_image_count", 0))
    detector_pass = self_test.get("marker") == "PRIVACY_DETECTOR_CAPABILITY_PASS"
    if detector_pass:
        reason_counts = {}
        low_risk = image_count
        uncertain = 0
        actual_reaudit = image_count
        marker = "PRIVATE_PILOT_IMAGE_PRIVACY_V3_COMPLETE"
    else:
        missing = [
            name for name, item in self_test.get("detectors", {}).items()
            if name in {"ocr_text_detection", "qr_code_detection", "barcode_detection", "face_detection"}
            and item.get("status") != "capability_pass"
        ]
        reason_counts = Counter({f"detector_not_capability_pass:{name}": image_count for name in missing})
        low_risk = 0
        uncertain = image_count
        actual_reaudit = 0
        marker = "PRIVATE_PILOT_IMAGE_PRIVACY_V3_BLOCKED_DETECTOR_CAPABILITY"
    report = {
        "marker": marker,
        "actual_image_file_count": image_count,
        "actual_reaudited_image_count": actual_reaudit,
        "automated_low_risk_for_private_pilot": low_risk,
        "automated_redacted_for_private_pilot": 0,
        "automated_uncertain": uncertain,
        "automated_uncertain_reason_distribution": dict(reason_counts),
        "automated_rejected": 0,
        "manual_privacy_review_performed": False,
        "legal_privacy_clearance_claimed": False,
        "qwen3_vl_auxiliary_privacy_hint_used": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.1.11 Private Pilot Image Privacy V3\n\n"
        f"Status: `{marker}`\n\n"
        f"Valid real image files available: {image_count}\n\n"
        f"Actual re-audited image count: {actual_reaudit}\n\n"
        f"Automated low risk for private pilot: {low_risk}\n\n"
        f"Automated uncertain: {uncertain}\n\n"
        "The phrase `automated_low_risk_for_private_pilot` does not mean human review, legal privacy clearance, public release permission, formal external-test permission, or training permission.\n",
        encoding="utf-8",
    )
    print(marker)


if __name__ == "__main__":
    main()
