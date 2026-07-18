from __future__ import annotations

from typing import Any, Dict

from app.data_governance.project_mode import evaluate_project_activity


def evaluate_research_scope(activity: str, source_type: str, data_type: str = "text", intended_output: str = "local_result") -> Dict[str, Any]:
    return evaluate_project_activity(activity, source_type, data_type, intended_output).to_dict()


def private_research_status() -> Dict[str, Any]:
    local_inference = evaluate_research_scope("local_model_inference", "synthetic_project_owned")
    exploratory = evaluate_research_scope("private_exploratory_evaluation", "amazon_reviews_2023")
    synthetic = evaluate_research_scope("synthetic_training", "synthetic_project_owned")
    public_pilot = evaluate_research_scope("public_pilot_local_processing", "amazon_reviews_2023")
    image_gate = False
    formal = evaluate_research_scope("formal_external_evaluation", "amazon_reviews_2023")
    restricted = evaluate_research_scope("restricted_data_training", "amazon_reviews_2023")
    release = evaluate_research_scope("public_result_release", "amazon_reviews_2023")
    return {
        "project_mode": "private_noncommercial_research",
        "technical_system_readiness": "PASS",
        "private_research_gate": "PASS" if local_inference["allowed"] and exploratory["allowed"] else "BLOCKED",
        "private_local_inference_allowed": local_inference["allowed"],
        "private_exploratory_evaluation_allowed": exploratory["allowed"],
        "synthetic_training_gate": "PASS" if synthetic["allowed"] else "BLOCKED",
        "public_pilot_local_read_only_allowed": public_pilot["allowed"],
        "private_public_pilot_image_inference_allowed": image_gate,
        "formal_research_evaluation": "BLOCKED" if not formal["allowed"] else "PASS",
        "authorized_data_manifest": "BLOCKED",
        "restricted_data_training": "BLOCKED" if not restricted["allowed"] else "PASS",
        "public_release": "BLOCKED" if not release["allowed"] else "PASS",
        "v161_final_gate": "BLOCKED_FORMAL_USE_ONLY",
        "PRIVATE_NONCOMMERCIAL_RESEARCH_MODE_ACTIVE": True,
        "PRIVATE_RESEARCH_GATE_PASS": local_inference["allowed"] and exploratory["allowed"],
        "PRIVATE_LOCAL_INFERENCE_ALLOWED": local_inference["allowed"],
        "PRIVATE_EXPLORATORY_EVALUATION_ALLOWED": exploratory["allowed"],
        "SYNTHETIC_TRAINING_GATE_PASS": synthetic["allowed"],
        "PUBLIC_PILOT_LOCAL_READ_ONLY_ALLOWED": public_pilot["allowed"],
        "PRIVATE_PUBLIC_PILOT_IMAGE_INFERENCE_BLOCKED": True,
        "FORMAL_RESEARCH_EVALUATION_BLOCKED": not formal["allowed"],
        "FORMAL_RELEASE_BLOCKED": not release["allowed"],
        "RESTRICTED_DATA_TRAINING_BLOCKED": not restricted["allowed"],
        "AUTHORIZED_DATA_MANIFEST_BLOCKED": True,
        "V162_PRIVATE_RESEARCH_GATE_PASS": local_inference["allowed"] and exploratory["allowed"],
    }
