import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run_script(name: str):
    return subprocess.run(
        [sys.executable, str(ROOT / "ai-service" / "scripts" / name)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def load_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_unrecoverable_locators_are_permanently_closed():
    run_script("close_unrecoverable_pilot_locators.py")
    result = load_json("data/real_world/audit/pilot_unrecoverable_locator_closure.json")

    assert result["marker"] == "PILOT_UNRECOVERABLE_LOCATORS_CLOSED"
    assert result["retry_allowed"] is False
    assert result["retry_disabled"] is True
    assert result["alternative_source_allowed"] is False
    assert result["third_party_recovery_prohibited"] is True


def test_dependency_inventory_records_missing_local_backends():
    run_script("audit_local_privacy_dependency_inventory.py")
    result = load_json("data/real_world/audit/local_privacy_dependency_inventory.json")
    packages = {item["package_or_binary"]: item for item in result["packages"]}

    assert result["marker"] == "LOCAL_PRIVACY_DEPENDENCY_INVENTORY_COMPLETE"
    assert "cv2" in packages
    assert "tesseract" in packages
    assert result["new_dependencies_installed"] == []


def test_synthetic_fixtures_are_not_real_pilot_data():
    run_script("build_privacy_detector_fixtures.py")
    fixture_dir = ROOT / "ai-service" / "tests" / "fixtures" / "privacy-detectors"

    assert (fixture_dir / "clean_product_like.png").exists()
    assert (fixture_dir / "phone_text.png").exists()
    assert (fixture_dir / "qr_code.png").exists()


def test_detector_self_test_blocks_import_only_capabilities_and_keeps_text_out_of_git():
    run_script("self_test_privacy_detectors.py")
    result = load_json("data/real_world/audit/privacy_detector_self_test.json")
    text = (ROOT / "data/real_world/audit/privacy_detector_self_test.json").read_text(encoding="utf-8")

    assert result["marker"] in {"PRIVACY_DETECTOR_CAPABILITY_BLOCKED", "PRIVACY_DETECTOR_CAPABILITY_PARTIAL"}
    assert result["synthetic_fixtures_counted_as_real_pilot"] is False
    assert result["qwen3_vl_replaces_mandatory_detectors"] is False
    assert result["ocr_full_text_in_git_report"] is False
    assert result["qr_full_content_in_git_report"] is False
    assert "555-123-4567" not in text
    assert "example.test" not in text


def test_private_image_privacy_v3_requires_capability_pass_before_low_risk():
    run_script("audit_private_pilot_image_privacy_v3.py")
    result = load_json("data/real_world/audit/private_pilot_image_privacy_v3.json")

    assert result["marker"] == "PRIVATE_PILOT_IMAGE_PRIVACY_V3_BLOCKED_DETECTOR_CAPABILITY"
    assert result["actual_image_file_count"] == 9
    assert result["actual_reaudited_image_count"] == 0
    assert result["automated_low_risk_for_private_pilot"] == 0
    assert result["legal_privacy_clearance_claimed"] is False


def test_vlm_compatibility_blocks_when_safe_real_images_less_than_five():
    run_script("run_private_real_image_vlm_compatibility.py")
    result = load_json("data/real_world/audit/private_real_image_vlm_compatibility.json")

    assert result["marker"] == "PRIVATE_REAL_IMAGE_VLM_COMPATIBILITY_BLOCKED"
    assert result["eligible_image_count"] < 5
    assert result["processed_image_count"] == 0
    assert result["real_vlm_inference_count"] == 0
    assert result["vlm_input_included_review_text"] is False
    assert result["visual_f1_calculated"] is False


def test_dataset_roles_are_frozen_and_do_not_unlock_rights_or_training():
    run_script("freeze_pilot_dataset_roles.py")
    result = load_json("data/real_world/audit/pilot_dataset_role_freeze.json")

    assert result["marker"] == "PILOT_DATASET_ROLES_FROZEN"
    assert result["AUTHORIZED_REAL_DATA_REQUIRED_FOR_FORMAL_EVALUATION"] is True
    assert result["FORMAL_REALWORLD_DATA_RIGHTS_READY"] is False
    assert result["SFT_DATA_READY"] is False
    assert all(source["external_evaluation_allowed"] is False for source in result["sources"])
