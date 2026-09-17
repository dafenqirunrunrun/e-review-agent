import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "real_world" / "audit" / "private_pilot_v2_scale_readiness.json"


def load(name):
    path = ROOT / "data" / "real_world" / "audit" / name
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    acquisition = load("private_pilot_v2_image_acquisition.json")
    privacy = load("private_pilot_v2_image_privacy.json")
    sampling = load("private_pilot_v2_sampling_report.json")
    duplicates = load("pilot_duplicate_audit.json")
    vlm = load("realworld_vlm_private_pilot.json")

    safe_images = privacy.get("automated_cleared", 0) + privacy.get("automated_redacted", 0)
    technical_checks = {
        "valid_multimodal_records_at_least_20": sampling.get("multimodal_record_count", 0) >= 20,
        "valid_images_at_least_20": acquisition.get("valid_image_count", 0) >= 20,
        "download_success_rate_at_least_0_80": acquisition.get("download_success_rate", 0) >= 0.80,
        "safe_images_at_least_5": safe_images >= 5,
        "REALWORLD_VLM_PILOT_PASS": vlm.get("marker") == "REALWORLD_VLM_PILOT_PASS",
        "final_schema_valid_rate_at_least_0_95": vlm.get("final_schema_valid_rate", 0) >= 0.95,
        "fallback_rate_at_most_0_10": vlm.get("fallback_rate", 1) <= 0.10,
        "oom_count_zero": vlm.get("oom_count", 0) == 0,
        "privacy_text_leak_count_zero": vlm.get("privacy_text_leak_count", 0) == 0,
        "duplicate_audit_complete": duplicates.get("marker") == "PILOT_DUPLICATE_AUDIT_COMPLETE",
    }
    technical_ready = all(technical_checks.values())
    rights_ready = False
    external_isolation_pass = True
    private_pilot_ready = technical_ready and rights_ready and external_isolation_pass

    report = {
        "marker": "PRIVATE_PILOT_V2_NOT_READY_FOR_SCALE" if not private_pilot_ready else "PRIVATE_PILOT_V2_READY_FOR_LARGER_INTERNAL_SCALE",
        "PRIVATE_MULTIMODAL_PILOT_TECHNICALLY_READY": technical_ready,
        "FORMAL_REALWORLD_DATA_RIGHTS_READY": rights_ready,
        "PRIVATE_PILOT_READY_FOR_LARGER_INTERNAL_SCALE": private_pilot_ready,
        "EXTERNAL_TEST_ISOLATION_AUDIT_PASS": external_isolation_pass,
        "technical_checks": technical_checks,
        "formal_external_test_allowed": False,
        "sft_allowed": False,
        "dpo_allowed": False,
        "release_tag_allowed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["marker"])


if __name__ == "__main__":
    main()
