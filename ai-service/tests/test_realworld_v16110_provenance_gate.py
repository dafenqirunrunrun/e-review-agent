import json
import re
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


def test_v16110_freeze_manifest_is_git_safe_and_non_overwriting():
    run_script("freeze_private_pilot_v1.py")
    result = load_json("data/real_world/audit/private_pilot_v1_freeze_manifest.json")
    text = json.dumps(result, ensure_ascii=False)

    assert result["marker"] in {"PRIVATE_PILOT_V1_FROZEN", "PRIVATE_PILOT_V1_FREEZE_BLOCKED"}
    assert "review_text" not in text
    assert "http://" not in text and "https://" not in text
    assert "source_record_id\"" not in text
    assert "data-private" not in text


def test_v16110_source_locator_recovery_never_guesses_urls_or_logs_urls():
    completed = run_script("recover_private_pilot_source_locators.py")
    result = load_json("data/real_world/audit/pilot_source_locator_recovery.json")
    text = (ROOT / "data/real_world/audit/pilot_source_locator_recovery.json").read_text(encoding="utf-8")

    assert "PILOT_SOURCE_LOCATOR_RECOVERY_" in completed.stdout
    assert result["source_snapshot_available"] is True
    assert result["recovered_locator_count"] == 0
    assert result["unrecoverable_count"] >= 1
    assert "http://" not in text and "https://" not in text
    assert result["signed_url_count"] == 0
    assert "image_id_guess" not in json.dumps(result)


def test_v16110_downloader_blocks_without_official_locator_and_no_substitution():
    run_script("download_private_pilot_images_v2.py")
    result = load_json("data/real_world/audit/private_pilot_v2_image_acquisition.json")

    assert result["download_attempt_count"] == 0
    assert result["download_success_count"] == 0
    assert result["substitute_image_used"] is False
    assert result["url_guessing_used"] is False
    assert result["failure_reason_counts"].get("locator_unrecoverable", 0) >= 1


def test_v16110_privacy_detector_capability_gate_blocks_clearance():
    run_script("audit_image_privacy_detector_capabilities.py")
    result = load_json("data/real_world/audit/image_privacy_detector_capabilities.json")

    assert result["marker"] == "PRIVACY_DETECTOR_CAPABILITY_BLOCKED"
    assert result["automated_clearance_allowed"] is False
    assert result["qwen3_vl_can_replace_mandatory_detectors"] is False
    for name in ["ocr_text_detection", "qr_code_detection", "barcode_detection", "face_detection"]:
        assert name in result["missing_mandatory_detectors"]


def test_v16110_image_privacy_v2_uncertain_when_mandatory_detectors_missing():
    run_script("audit_private_pilot_images_v2.py")
    result = load_json("data/real_world/audit/private_pilot_v2_image_privacy.json")

    assert result["automated_cleared"] == 0
    assert result["automated_redacted"] == 0
    assert result["automated_uncertain"] == 18
    assert result["automated_uncertain_reason_distribution"]["automated_uncertain_detector_unavailable"] == 18
    assert result["qwen3_vl_used_for_clearance"] is False


def test_v16110_domain_taxonomy_excludes_asap_from_ecommerce_denominator():
    run_script("audit_private_pilot_domain_and_taxonomy_fit.py")
    result = load_json("data/real_world/audit/private_pilot_domain_taxonomy_fit.json")

    assert result["marker"] == "PILOT_TAXONOMY_PRELIMINARY_ONLY"
    assert result["asap_enters_ecommerce_taxonomy_denominator"] is False
    assert result["sources"]["asap_chinese_reviews"]["ecommerce_denominator_excluded"] is True
    assert result["sources"]["asap_chinese_reviews"]["adjusted_mappable_rate"] == 0.0
    assert result["ecommerce_source_adjusted_mappable_rate"] > result["overall_adjusted_mappable_rate"]
    assert result["weak_labels_are_gold"] is False


def test_v16110_risk_focused_v2_sampling_is_not_gold_or_external_test():
    run_script("build_private_pilot_v2_sampling.py")
    result = load_json("data/real_world/audit/private_pilot_v2_sampling_report.json")
    text = json.dumps(result, ensure_ascii=False).lower()

    assert result["annotation_source"] == "heuristic_candidate_status"
    assert result["annotation_reliability"] == "unverified"
    assert result["not_gold_label"] is True
    assert result["not_external_test"] is True
    assert result["not_sft"] is True
    assert "review_text" not in text
    assert not re.search(r"https?://", text)


def test_v16110_scale_readiness_keeps_formal_rights_blocked():
    run_script("audit_pilot_duplicates.py")
    run_script("audit_private_pilot_v2_readiness.py")
    result = load_json("data/real_world/audit/private_pilot_v2_scale_readiness.json")

    assert result["FORMAL_REALWORLD_DATA_RIGHTS_READY"] is False
    assert result["PRIVATE_PILOT_READY_FOR_LARGER_INTERNAL_SCALE"] is False
    assert result["formal_external_test_allowed"] is False
    assert result["sft_allowed"] is False
    assert result["release_tag_allowed"] is False
