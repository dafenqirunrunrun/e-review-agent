import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-service"))

from app.data_governance.authorization_gate import evaluate_authorization  # noqa: E402


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


def load_json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def manifest(**overrides):
    base = {
        "source": {
            "source_id": "authorized_demo",
            "source_name": "Demo",
            "data_owner": "owner-reference",
            "data_controller": "controller-reference",
            "provider_contact_reference": "contact-reference",
            "authorization_basis": "explicit_written_authorization",
        },
        "authorization": {
            "authorized_by": "approver-reference",
            "authorized_at": "2026-01-01",
            "authorization_document_reference": "AUTH-DOC-REF",
            "authorization_expiry": "2027-01-01",
        },
        "allowed_uses": {
            "internal_development": True,
            "internal_evaluation": True,
            "formal_external_evaluation": False,
            "model_training": False,
            "llm_sft": False,
            "vlm_sft": False,
            "dpo": False,
            "case_corpus": False,
            "rag_index": False,
            "derived_statistics": True,
            "publication_of_aggregate_results": True,
            "redistribution_of_text": False,
            "redistribution_of_images": False,
            "publication_of_redacted_examples": False,
        },
        "data_scope": {
            "review_text": True,
            "ratings": True,
            "product_categories": True,
            "user_review_images": False,
            "order_metadata": False,
            "customer_service_dialogue": False,
            "labels": False,
        },
        "privacy": {
            "contains_personal_data": False,
            "deidentification_required": True,
            "image_redaction_required": True,
            "retention_period_days": 365,
            "deletion_required_after_expiry": True,
            "cross_border_transfer_allowed": False,
        },
        "annotation": {
            "existing_labels_available": False,
            "label_owner": "",
            "annotation_usage_allowed": False,
            "reannotation_allowed": False,
        },
        "approval": {
            "project_approval_status": "approved",
            "approved_by_project_owner": True,
            "reviewed_at": "2026-01-02",
            "note": "",
        },
    }
    for key, value in overrides.items():
        base[key] = value
    return base


def test_authorization_manifest_missing_is_incomplete_blocked():
    decision = evaluate_authorization(None, "internal_evaluation", "text")

    assert decision.decision == "incomplete"
    assert "authorization_manifest_missing" in decision.reason_codes


def test_owner_approval_false_routes_to_quarantine_not_validated():
    data = manifest(approval={"project_approval_status": "pending", "approved_by_project_owner": False})
    decision = evaluate_authorization(data, "internal_evaluation", "text")

    assert decision.decision == "blocked"
    assert "project_owner_approval_missing" in decision.reason_codes


def test_expired_authorization_blocks_use():
    data = manifest()
    data["authorization"]["authorization_expiry"] = (date.today() - timedelta(days=1)).isoformat()
    decision = evaluate_authorization(data, "internal_evaluation", "text")

    assert decision.decision == "expired"
    assert "authorization_expired" in decision.reason_codes


def test_text_authorization_does_not_approve_images_or_training_or_redistribution():
    data = manifest()

    assert evaluate_authorization(data, "internal_evaluation", "text").decision == "allowed"
    assert evaluate_authorization(data, "internal_evaluation", "image").decision == "blocked"
    assert evaluate_authorization(data, "llm_sft", "text").decision == "blocked"
    assert evaluate_authorization(data, "redistribution", "text").decision == "blocked"


def test_external_eval_and_rag_index_are_independently_blocked():
    data = manifest()

    assert evaluate_authorization(data, "formal_external_evaluation", "text").decision == "blocked"
    assert evaluate_authorization(data, "rag_index", "text").decision == "blocked"


def test_public_pilot_freeze_and_roles_keep_pilot_out_of_authorized_data():
    run_script("freeze_public_pilot_final.py")
    run_script("audit_authorized_dataset_leakage.py")
    freeze = load_json("data/real_world/audit/public_pilot_final_freeze.json")
    leakage = load_json("data/authorized_intake/audit/authorized_dataset_leakage_audit.json")

    assert freeze["marker"] == "PUBLIC_REALWORLD_PILOT_FROZEN"
    assert freeze["further_acquisition_allowed"] is False
    assert freeze["formal_evaluation_allowed"] is False
    assert leakage["PUBLIC_PILOT_EXCLUDED_FROM_AUTHORIZED_DATA"] is True
    assert leakage["marker"] == "AUTHORIZED_DATA_ISOLATION_PASS"


def test_dry_run_intake_does_not_write_validated_data_without_authorization(tmp_path):
    input_path = tmp_path / "reviews.jsonl"
    input_path.write_text('{"source_record_id":"r1","review_text":"hello"}\n', encoding="utf-8")
    run_script(
        "intake_authorized_dataset.py",
        "--input-path",
        str(input_path),
        "--source-id",
        "no_manifest",
        "--intended-use",
        "internal_evaluation",
    )
    summary = load_json("data/authorized_intake/audit/intake_run_summary.json")

    assert summary["marker"] == "AUTHORIZED_DATA_INTAKE_DRY_RUN"
    assert summary["authorization_decision"]["decision"] == "incomplete"
    assert summary["validated_count"] == 0
    assert summary["validated_write_performed"] is False


def test_text_redaction_summary_does_not_store_raw_text(tmp_path):
    input_path = tmp_path / "raw.txt"
    phone = "555" + "-123" + "-4567"
    email = "test.person" + "@" + "example" + ".test"
    input_path.write_text(f"Call {phone} or mail {email}", encoding="utf-8")
    run_script("redact_authorized_review_text.py", "--input", str(input_path))
    summary = load_json("data/authorized_intake/statistics/redaction_summary.json")
    text = (ROOT / "data/authorized_intake/statistics/redaction_summary.json").read_text(encoding="utf-8")

    assert summary["marker"] == "AUTHORIZED_TEXT_REDACTION_SUMMARY"
    assert summary["replacement_counts"]["PHONE"] == 1
    assert summary["replacement_counts"]["EMAIL"] == 1
    assert phone not in text
    assert email not in text


def test_splits_sft_and_technical_readiness_are_separate_from_formal_readiness():
    run_script("build_authorized_dataset_splits.py")
    run_script("audit_authorized_sft_readiness.py")
    run_script("freeze_technical_capability.py")

    splits = load_json("data/authorized_intake/split_manifest/authorized_dataset_splits.json")
    sft = load_json("data/authorized_intake/audit/authorized_sft_readiness.json")
    tech = load_json("data/authorized_intake/audit/technical_capability_freeze.json")

    assert splits["marker"] == "AUTHORIZED_DATA_SPLIT_BLOCKED_NO_DATA"
    assert splits["external_test_excluded_from_sft"] is True
    assert sft["AUTHORIZED_SFT_DATA_READY"] is False
    assert sft["AUTHORIZED_VLM_SFT_DATA_READY"] is False
    assert tech["TECHNICAL_SYSTEM_READINESS_PASS"] is True
    assert tech["RESEARCH_EVALUATION_READINESS_BLOCKED"] is True
