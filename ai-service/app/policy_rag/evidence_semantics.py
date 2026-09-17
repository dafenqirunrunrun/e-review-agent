from __future__ import annotations

from collections.abc import Iterable

from app.contracts.review_semantics import risk_type_evidence_tags
from app.policy_rag.models import PolicySearchResult


# This is the business contract used by both Reflection and evidence selection.
# A selector may only prioritize an evidence item when it meets this same policy
# support definition; it never upgrades an unsupported risk to supported.
RISK_TO_REQUIRED_TAGS: dict[str, set[str]] = {
    "fake_review": {"fake_engagement", "incentivized_review", "fake_review", "rating_manipulation"},
    "rating_manipulation": {"incentivized_review", "rating_manipulation", "fake_engagement"},
    "review_suppression": {"review_suppression"},
    "privacy_risk": {"privacy"},
    "after_sales_risk": {"after_sales", "after_sales_risk"},
    "safety_or_fraud_risk": {"safety_or_fraud", "safety_or_fraud_risk"},
    "harassment_or_abuse": {"harassment_or_abuse"},
}


def governed_risk_types(risk_types: Iterable[str]) -> list[str]:
    """Return policy-governed risks once, preserving the detected-risk order."""
    return list(dict.fromkeys(risk for risk in risk_types if risk in RISK_TO_REQUIRED_TAGS))


def required_evidence_tags(risk_type: str) -> set[str]:
    return set(RISK_TO_REQUIRED_TAGS.get(risk_type, risk_type_evidence_tags(risk_type) or (risk_type,)))


def evidence_supports_risk(risk_type: str, evidence: PolicySearchResult) -> bool:
    observed = set(evidence.evidenceTags) | set(evidence.riskTypes)
    return bool(observed.intersection(required_evidence_tags(risk_type)))
