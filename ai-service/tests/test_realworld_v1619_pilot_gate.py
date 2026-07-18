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


def test_v1619_image_retry_does_not_substitute_missing_images():
    completed = run_script("retry_pilot_image_downloads.py")
    result = json.loads((ROOT / "data/real_world/audit/pilot_image_download_retry.json").read_text(encoding="utf-8"))

    assert "PILOT_IMAGE_ACQUISITION_PARTIAL" in completed.stdout
    assert result["images_expected"] == 18
    assert result["images_total_downloaded"] == 9
    assert result["images_newly_downloaded"] == 0
    assert result["source_url_not_retained_count"] == 9
    assert result["final_download_success_rate"] == 0.5


def test_v1619_privacy_uncertain_images_do_not_enter_vlm_pilot():
    run_script("audit_pilot_image_privacy.py")
    run_script("redact_pilot_image_privacy.py")
    run_script("audit_pilot_vlm_eligibility.py")
    completed = run_script("run_realworld_vlm_private_pilot.py")
    privacy = json.loads((ROOT / "data/real_world/audit/pilot_image_privacy_audit.json").read_text(encoding="utf-8"))
    eligibility = json.loads((ROOT / "data/real_world/audit/pilot_vlm_eligibility.json").read_text(encoding="utf-8"))
    vlm = json.loads((ROOT / "data/real_world/audit/realworld_vlm_private_pilot.json").read_text(encoding="utf-8"))

    assert privacy["automated_uncertain"] == 18
    assert privacy["automated_cleared"] == 0
    assert eligibility["eligible_record_count"] == 0
    assert "REALWORLD_VLM_PILOT_BLOCKED_INSUFFICIENT_SAFE_IMAGES" in completed.stdout
    assert vlm["real_vlm_inference_count"] == 0


def test_v1619_taxonomy_quality_allows_gaps_and_blocks_forced_mapping():
    run_script("audit_pilot_taxonomy_mapping_quality.py")
    result = json.loads((ROOT / "data/real_world/audit/pilot_taxonomy_mapping_quality.json").read_text(encoding="utf-8"))

    assert result["raw_mappable_rate"] == 1.0
    assert result["adjusted_mappable_rate"] < result["raw_mappable_rate"]
    assert result["insufficient_evidence_count"] > 0
    assert result["default_mapping_count"] == 0
    assert result["forced_mapping_count"] == 0


def test_v1619_duplicate_and_scale_readiness_gates_are_explicit():
    run_script("audit_pilot_duplicates.py")
    run_script("audit_pilot_scale_readiness.py")
    duplicate = json.loads((ROOT / "data/real_world/audit/pilot_duplicate_audit.json").read_text(encoding="utf-8"))
    readiness = json.loads((ROOT / "data/real_world/audit/pilot_scale_readiness.json").read_text(encoding="utf-8"))

    assert duplicate["marker"] == "PILOT_DUPLICATE_AUDIT_COMPLETE"
    assert "perceptual_image_duplicate" in duplicate
    assert readiness["marker"] == "REALWORLD_PILOT_NOT_READY_FOR_SCALE"
    assert "REALWORLD_VLM_PILOT_PASS" in readiness["unmet_requirements"]
    assert readiness["checks"]["EXTERNAL_TEST_ISOLATION_AUDIT_PASS"] is True


def test_v1619_git_aggregate_manifest_has_no_raw_text_or_urls():
    manifest = (ROOT / "data/real_world/pilot_manifest/private_pilot_aggregate_manifest.jsonl").read_text(encoding="utf-8")
    privacy_manifest = (ROOT / "data/real_world/pilot_manifest/image_privacy_aggregate_manifest.jsonl").read_text(encoding="utf-8")

    for text in [manifest, privacy_manifest]:
        assert "review_text" not in text
        assert "image_url" not in text
        assert "m.media-amazon" not in text
        assert "user_id" not in text
