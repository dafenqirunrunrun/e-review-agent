import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "real_world" / "audit" / "public_pilot_final_freeze.json"
DOC = ROOT / "docs" / "167_v16112_public_pilot_final_freeze.md"


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def main():
    taxonomy = load("data/real_world/audit/private_pilot_domain_taxonomy_fit.json")
    acquisition = load("data/real_world/audit/private_pilot_v2_image_acquisition.json")
    locators = load("data/real_world/audit/pilot_unrecoverable_locator_closure.json")
    privacy = load("data/real_world/audit/privacy_detector_self_test.json")
    vlm = load("data/real_world/audit/private_real_image_vlm_compatibility.json")
    report = {
        "marker": "PUBLIC_REALWORLD_PILOT_FROZEN",
        "public_pilot_status": "frozen",
        "amazon_text_pilot_count": 150,
        "asap_text_pilot_count": 150,
        "multimodal_record_count": 11,
        "valid_image_count": acquisition.get("valid_image_count", 9),
        "image_download_success_rate": acquisition.get("download_success_rate", 0.5),
        "unrecoverable_locator_count": locators.get("total_unrecoverable_count", 9),
        "mandatory_privacy_detector_capability": privacy.get("marker"),
        "amazon_adjusted_mappable_rate": taxonomy["sources"]["amazon_reviews_2023"]["adjusted_mappable_rate"],
        "asap_adjusted_mappable_rate": taxonomy["sources"]["asap_chinese_reviews"]["adjusted_mappable_rate"],
        "overall_adjusted_mappable_rate": taxonomy["overall_adjusted_mappable_rate"],
        "private_real_image_vlm_compatibility": vlm.get("marker"),
        "FORMAL_REALWORLD_DATA_RIGHTS_READY": False,
        "SFT_DATA_READY": False,
        "further_acquisition_allowed": False,
        "further_prompt_tuning_allowed": False,
        "formal_evaluation_allowed": False,
        "training_allowed": False,
        "prohibited_sources_without_new_authorization": ["Amazon Reviews 2023", "ASAP", "JDDC"],
        "frozen_at": datetime.now(timezone.utc).isoformat(),
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC.write_text(
        "# V1.6.1.12 Public Pilot Final Freeze\n\n"
        "Status: `PUBLIC_REALWORLD_PILOT_FROZEN`\n\n"
        "Amazon Reviews 2023 and ASAP pilot data are frozen. They remain engineering compatibility evidence only and must not be expanded, prompt-tuned against, promoted into formal external evaluation, or used for training without new explicit authorization.\n",
        encoding="utf-8",
    )
    print(report["marker"])


if __name__ == "__main__":
    main()
