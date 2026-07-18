import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-service"))

from app.data_governance import project_mode
from app.data_governance.authorization_gate import evaluate_authorization
from app.data_governance.project_mode import ProjectMode, evaluate_project_activity, load_project_mode_policy
from app.data_governance.research_scope_gate import private_research_status
from app.main import app


def test_missing_project_mode_config_defaults_to_strict(monkeypatch, tmp_path):
    monkeypatch.setattr(project_mode, "PROJECT_MODE_CONFIG", tmp_path / "missing.yaml")
    monkeypatch.delenv("E_REVIEW_PROJECT_MODE", raising=False)

    policy = load_project_mode_policy()

    assert policy.project_mode == ProjectMode.STRICT_AUTHORIZED_RESEARCH


def test_private_mode_allows_local_noncommercial_activities():
    assert evaluate_project_activity("local_model_inference", "synthetic_project_owned").allowed is True
    assert evaluate_project_activity("private_exploratory_evaluation", "amazon_reviews_2023").allowed is True
    assert evaluate_project_activity("private_rag_evaluation", "asap_chinese_reviews").allowed is True


def test_private_mode_allows_project_owned_synthetic_training_only():
    synthetic = evaluate_project_activity("synthetic_training", "synthetic_project_owned")
    amazon = evaluate_project_activity("synthetic_training", "amazon_reviews_2023")

    assert synthetic.allowed is True
    assert synthetic.reason_codes == ["PROJECT_OWNED_SYNTHETIC_TRAINING"]
    assert amazon.allowed is False
    assert "PUBLIC_PILOT_TRAINING_RIGHTS_UNVERIFIED" in amazon.reason_codes


def test_private_mode_blocks_unknown_and_formal_or_release_activities():
    assert evaluate_project_activity("local_model_inference", "unknown_or_untracked").allowed is False
    assert evaluate_project_activity("formal_external_evaluation", "amazon_reviews_2023").allowed is False
    assert evaluate_project_activity("public_result_release", "amazon_reviews_2023").allowed is False
    assert evaluate_project_activity("model_weight_distribution", "synthetic_project_owned").allowed is False


def test_public_pilot_prompt_development_is_conditionally_allowed_only():
    decision = evaluate_project_activity("public_pilot_prompt_development", "amazon_reviews_2023")

    assert decision.allowed is True
    assert decision.decision == "conditionally_allowed"
    assert "not_external_test" in decision.restrictions
    assert "not_release_gate_evidence" in decision.restrictions


def test_authorization_gate_private_research_semantics_do_not_unlock_formal_use():
    manifest = {"source_type": "amazon_reviews_2023", "source": {"source_id": "amazon_reviews_2023"}}

    local = evaluate_authorization(manifest, "internal_evaluation", "text")
    sft = evaluate_authorization(manifest, "llm_sft", "text")
    formal = evaluate_authorization(manifest, "formal_external_evaluation", "text")

    assert local.decision == "conditionally_allowed"
    assert "PRIVATE_LOCAL_RESEARCH_SCOPE" in local.reason_codes
    assert sft.decision == "blocked"
    assert "PUBLIC_PILOT_TRAINING_RIGHTS_UNVERIFIED" in sft.reason_codes
    assert formal.decision in {"incomplete", "blocked"}


def test_synthetic_authorization_gate_training_path_is_project_owned_only():
    manifest = {"source_type": "synthetic_project_owned"}
    decision = evaluate_authorization(manifest, "llm_sft", "text")

    assert decision.decision == "allowed"
    assert "PROJECT_OWNED_SYNTHETIC_TRAINING" in decision.reason_codes


def test_private_research_status_keeps_formal_and_image_gates_blocked():
    status = private_research_status()

    assert status["PRIVATE_NONCOMMERCIAL_RESEARCH_MODE_ACTIVE"] is True
    assert status["PRIVATE_RESEARCH_GATE_PASS"] is True
    assert status["PRIVATE_LOCAL_INFERENCE_ALLOWED"] is True
    assert status["PRIVATE_EXPLORATORY_EVALUATION_ALLOWED"] is True
    assert status["SYNTHETIC_TRAINING_GATE_PASS"] is True
    assert status["PUBLIC_PILOT_LOCAL_READ_ONLY_ALLOWED"] is True
    assert status["private_public_pilot_image_inference_allowed"] is False
    assert status["formal_research_evaluation"] == "BLOCKED"
    assert status["public_release"] == "BLOCKED"
    assert status["v161_final_gate"] == "BLOCKED_FORMAL_USE_ONLY"


def test_system_readiness_endpoint_reports_private_mode_status():
    client = TestClient(app)
    response = client.get("/api/v1/system/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_mode"] == "private_noncommercial_research"
    assert payload["technical_system_readiness"] == "PASS"
    assert payload["private_research_gate"] == "PASS"
    assert payload["authorized_data_manifest"] == "BLOCKED"
