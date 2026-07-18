import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run_script(name: str, *args: str):
    return subprocess.run(
        [sys.executable, str(ROOT / "ai-service" / "scripts" / name), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_source_license_audit_blocks_unapproved_candidates():
    completed = run_script("audit_realworld_source_licenses.py")

    assert "REALWORLD_SOURCE_LICENSE_AUDIT_BLOCKED" in completed.stdout
    result = json.loads((ROOT / "data/real_world/audit/source_license_audit.json").read_text(encoding="utf-8"))
    assert result["marker"] == "REALWORLD_SOURCE_LICENSE_AUDIT_BLOCKED"
    assert result["approved_text_source_count"] == 0
    assert result["approved_multimodal_source_count"] == 0


def test_unapproved_text_source_is_rejected():
    completed = run_script("acquire_public_real_reviews.py", "--source-id", "amazon_reviews_2023_mccauley")

    assert "REAL_TEXT_DATA_SOURCE_NOT_AVAILABLE" in completed.stdout


def test_unapproved_or_text_only_image_source_is_rejected():
    run_script("delegate_realworld_source_approval.py")
    completed = run_script("acquire_public_review_images.py", "--source-id", "asap_chinese_reviews")

    assert "REAL_MULTIMODAL_DATA_SOURCE_NOT_AVAILABLE" in completed.stdout


def test_v1618_delegated_source_approval_records_user_delegation_without_legal_certification():
    completed = run_script("delegate_realworld_source_approval.py")

    assert "DELEGATED_SOURCE_APPROVAL_COMPLETE" in completed.stdout
    approval = (ROOT / "data/real_world/source_manifest/manual_source_approval.yaml").read_text(encoding="utf-8")
    status = json.loads((ROOT / "data/real_world/audit/source_approval_status.json").read_text(encoding="utf-8"))

    assert "approved_by_user: true" in approval
    assert 'approval_method: "delegated_conservative_evidence_review"' in approval
    assert "legal_certification: false" in approval
    assert status["approved_by_user"] is True
    assert status["approval_method"] == "delegated_conservative_evidence_review"
    assert status["legal_certification"] is False
    assert "REAL_TEXT_PILOT_ACQUISITION_ALLOWED" == status["text_pilot_status"]


def test_v1617_rights_are_not_implicitly_expanded_between_modalities():
    run_script("delegate_realworld_source_approval.py")
    delegated = [
        json.loads(line)
        for line in (ROOT / "data/real_world/source_manifest/delegated_approved_sources.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    asap = next(row for row in delegated if row["source_id"] == "asap_chinese_reviews")
    amazon = next(row for row in delegated if row["source_id"] == "amazon_reviews_2023")

    assert asap["contains_review_text"] is True
    assert asap["contains_images"] is False
    assert asap["image_internal_inference_allowed"] is False
    assert asap["model_training_allowed"] is False
    assert asap["redistribution_allowed"] is False
    assert amazon["image_download_allowed"] is True
    assert amazon["model_training_allowed"] is False
    assert amazon["redistribution_allowed"] is False


def test_v1618_private_pilot_keeps_raw_data_outside_git_and_blocks_vlm_until_privacy_clearance():
    run_script("delegate_realworld_source_approval.py")
    completed = run_script("run_private_realworld_pilot.py")

    assert "REALWORLD_PRIVATE_PILOT_COMPLETE" in completed.stdout
    result = json.loads((ROOT / "data/real_world/audit/private_pilot_status.json").read_text(encoding="utf-8"))
    manifest_text = (ROOT / "data/real_world/pilot_manifest/private_pilot_aggregate_manifest.jsonl").read_text(encoding="utf-8")
    assert result["text_pilot_count"] <= 300
    assert result["image_download_attempted"] <= 20
    assert result["git_excluded_raw_data"] is True
    assert result["external_test"] is False
    assert result["sft"] is False
    assert result["vlm_pilot_status"] == "REALWORLD_VLM_PILOT_BLOCKED"
    assert "review_text" not in manifest_text
    assert "image_url" not in manifest_text
    assert "user_id" not in manifest_text


def test_v1617_taxonomy_coverage_blocks_without_approved_pilot():
    run_script("delegate_realworld_source_approval.py")
    completed = run_script("run_private_realworld_pilot.py")

    result = json.loads((ROOT / "data/real_world/audit/pilot_taxonomy_coverage.json").read_text(encoding="utf-8"))
    assert result["marker"] == "REALWORLD_TAXONOMY_PILOT_AUDIT_COMPLETE"
    assert result["coverage_ready"] is True
    assert result["external_test"] is False
    assert result["sft"] is False


def test_text_pii_redaction_helper_masks_sensitive_values():
    sys.path.insert(0, str(ROOT / "ai-service" / "scripts"))
    from realworld_data_policy import redact_text

    phone = "138" + "1234" + "5678"
    redacted, hits = redact_text(f"phone {phone} order 123456 address demo-road")

    assert hits >= 3
    assert phone not in redacted
    assert "123456" not in redacted


def test_realworld_eval_scripts_block_without_external_sets():
    for script, marker in [
        ("eval_realworld_text_rag_external.py", "REALWORLD_TEXT_RAG_EVAL_BLOCKED"),
        ("eval_realworld_qwen_text_external.py", "REALWORLD_TEXT_QWEN_EVAL_BLOCKED"),
        ("eval_realworld_vlm_external.py", "REALWORLD_VLM_EVAL_BLOCKED"),
        ("eval_realworld_multimodal_ablation.py", "REALWORLD_MULTIMODAL_ABLATION_BLOCKED"),
        ("calibrate_realworld_multimodal_route.py", "REALWORLD_MULTIMODAL_ROUTE_CALIBRATION_BLOCKED"),
        ("audit_realworld_sft_readiness.py", "SFT_DATA_NOT_READY"),
    ]:
        completed = run_script(script)
        assert marker in completed.stdout


def test_external_test_isolation_covers_new_realworld_paths():
    completed = run_script("audit_external_test_isolation.py")

    assert "EXTERNAL_TEST_ISOLATION_AUDIT_PASS" in completed.stdout
    result = json.loads((ROOT / "data/multimodal/audit/external_test_isolation_audit.json").read_text(encoding="utf-8"))
    assert result["violations"] == []
    assert result["index_metadata_violations"] == []
