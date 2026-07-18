from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional

from app.data_governance.project_mode import evaluate_project_activity, load_project_mode_policy, ProjectMode


INTENDED_USE_TO_FIELD = {
    "private_processing": "internal_development",
    "internal_evaluation": "internal_evaluation",
    "formal_external_evaluation": "formal_external_evaluation",
    "rag_index": "rag_index",
    "llm_sft": "llm_sft",
    "vlm_sft": "vlm_sft",
    "dpo": "dpo",
    "aggregate_reporting": "derived_statistics",
    "example_publication": "publication_of_redacted_examples",
    "redistribution": "redistribution_of_text",
}

DATA_TYPE_TO_FIELD = {
    "text": "review_text",
    "image": "user_review_images",
    "multimodal": "user_review_images",
    "annotation": "labels",
}


@dataclass
class AuthorizationDecision:
    decision: str
    reason_codes: List[str]
    missing_fields: List[str]
    conflicting_fields: List[str]
    authorization_reference: Optional[str]
    evaluated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _get_path(manifest: Dict[str, Any], dotted: str) -> Any:
    value: Any = manifest
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _missing_required(manifest: Dict[str, Any], fields: Iterable[str]) -> List[str]:
    missing = []
    for field in fields:
        value = _get_path(manifest, field)
        if value in (None, ""):
            missing.append(field)
    return missing


def _parse_date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None


def evaluate_authorization(
    manifest: Optional[Dict[str, Any]],
    intended_use: str,
    data_type: str,
    current_date: Optional[date] = None,
) -> AuthorizationDecision:
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    policy = load_project_mode_policy()
    if policy.project_mode == ProjectMode.PRIVATE_NONCOMMERCIAL_RESEARCH:
        source_type = None if manifest is None else str(manifest.get("source_type") or manifest.get("source", {}).get("source_id") or "")
        private_activities = {
            "private_processing": "public_pilot_local_processing",
            "internal_evaluation": "private_exploratory_evaluation",
        }
        if source_type in {"amazon_reviews_2023", "asap_chinese_reviews"} and intended_use in private_activities:
            decision = evaluate_project_activity(private_activities[intended_use], source_type, data_type, "local_result")
            if decision.allowed:
                return AuthorizationDecision(
                    "conditionally_allowed",
                    ["PRIVATE_LOCAL_RESEARCH_SCOPE"],
                    [],
                    [],
                    None if manifest is None else _get_path(manifest, "authorization.authorization_document_reference"),
                    now,
                )
        if source_type == "synthetic_project_owned" and intended_use in {"llm_sft", "private_processing"}:
            decision = evaluate_project_activity("synthetic_training", source_type, data_type, "local_model_adapter")
            if decision.allowed:
                return AuthorizationDecision("allowed", ["PROJECT_OWNED_SYNTHETIC_TRAINING"], [], [], None, now)
        if source_type in {"amazon_reviews_2023", "asap_chinese_reviews"} and intended_use in {"llm_sft", "vlm_sft", "dpo"}:
            return AuthorizationDecision("blocked", ["PUBLIC_PILOT_TRAINING_RIGHTS_UNVERIFIED"], [], [intended_use], None, now)

    if manifest is None:
        return AuthorizationDecision("incomplete", ["authorization_manifest_missing"], ["manifest"], [], None, now)

    required = [
        "source.source_id",
        "source.data_owner",
        "source.authorization_basis",
        "authorization.authorized_by",
        "authorization.authorized_at",
        "authorization.authorization_document_reference",
        "approval.project_approval_status",
    ]
    missing = _missing_required(manifest, required)
    authorization_reference = _get_path(manifest, "authorization.authorization_document_reference")
    if missing:
        return AuthorizationDecision("incomplete", ["required_authorization_fields_missing"], missing, [], authorization_reference, now)

    approval = manifest.get("approval", {})
    if approval.get("approved_by_project_owner") is not True or approval.get("project_approval_status") != "approved":
        return AuthorizationDecision("blocked", ["project_owner_approval_missing"], [], ["approval.approved_by_project_owner"], authorization_reference, now)

    expiry = _parse_date(_get_path(manifest, "authorization.authorization_expiry"))
    today = current_date or date.today()
    if expiry and expiry < today:
        return AuthorizationDecision("expired", ["authorization_expired"], [], [], authorization_reference, now)

    use_field = INTENDED_USE_TO_FIELD.get(intended_use)
    if use_field is None:
        return AuthorizationDecision("conflicting", ["unknown_intended_use"], [], [intended_use], authorization_reference, now)
    if manifest.get("allowed_uses", {}).get(use_field) is not True:
        return AuthorizationDecision("blocked", [f"allowed_uses.{use_field}_false"], [], [f"allowed_uses.{use_field}"], authorization_reference, now)

    scope_field = DATA_TYPE_TO_FIELD.get(data_type)
    if scope_field is None:
        return AuthorizationDecision("conflicting", ["unknown_data_type"], [], [data_type], authorization_reference, now)
    if manifest.get("data_scope", {}).get(scope_field) is not True:
        return AuthorizationDecision("blocked", [f"data_scope.{scope_field}_false"], [], [f"data_scope.{scope_field}"], authorization_reference, now)

    if data_type in {"image", "multimodal"} and manifest.get("allowed_uses", {}).get("redistribution_of_images") is True:
        if manifest.get("privacy", {}).get("image_redaction_required") is None:
            return AuthorizationDecision("incomplete", ["image_privacy_policy_missing"], ["privacy.image_redaction_required"], [], authorization_reference, now)

    return AuthorizationDecision("allowed", ["authorization_allowed"], [], [], authorization_reference, now)
