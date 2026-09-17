import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRIVACY = ROOT / "data" / "real_world" / "audit" / "private_pilot_image_privacy_v3.json"
OUT = ROOT / "data" / "real_world" / "audit" / "private_real_image_vlm_compatibility.json"


def main():
    privacy = json.loads(PRIVACY.read_text(encoding="utf-8"))
    eligible = int(privacy.get("automated_low_risk_for_private_pilot", 0)) + int(privacy.get("automated_redacted_for_private_pilot", 0))
    if eligible < 5:
        marker = "PRIVATE_REAL_IMAGE_VLM_COMPATIBILITY_BLOCKED"
        processed = 0
    else:
        marker = "PRIVATE_REAL_IMAGE_VLM_COMPATIBILITY_BLOCKED"
        processed = 0
    report = {
        "marker": marker,
        "eligible_image_count": eligible,
        "eligible_record_count": eligible,
        "processed_image_count": processed,
        "file_read_success_rate": 0.0,
        "real_vlm_inference_count": 0,
        "real_vlm_success_rate": 0.0,
        "raw_schema_valid_rate": 0.0,
        "final_schema_valid_rate": 0.0,
        "deterministic_normalization_rate": 0.0,
        "safe_repair_rate": 0.0,
        "fallback_rate": 0.0,
        "oom_count": 0,
        "privacy_text_leak_count": 0,
        "unsupported_business_action_count": 0,
        "obvious_invalid_visual_claim_count": 0,
        "empty_visual_evidence_rate": 0.0,
        "uncertain_output_rate": 0.0,
        "avg_generate_ms": None,
        "p95_generate_ms": None,
        "active_session_wall_clock_ms": 0,
        "gpu_wait_ms": 0,
        "visual_f1_calculated": False,
        "risk_macro_f1_calculated": False,
        "vlm_input_included_review_text": False,
        "vlm_input_included_rating": False,
        "vlm_input_included_label": False,
        "blocked_reason": "eligible_image_count_less_than_5",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(marker)


if __name__ == "__main__":
    main()
