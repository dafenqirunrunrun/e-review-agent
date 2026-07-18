from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HumanReviewDecision:
    review_required: bool
    review_reason_codes: list[str]
    evidence_summary: str
    missing_information: list[str] = field(default_factory=list)
    recommended_next_step: str = "manual_review"


class HumanReviewRouter:
    def route(
        self,
        *,
        risk_level: str,
        fallback: bool = False,
        evidence_conflict: bool = False,
        insufficient_evidence: bool = False,
        unsupported_claim: bool = False,
        prompt_injection: bool = False,
        prohibited_action: bool = False,
        schema_repeated_failure: bool = False,
        tool_failure: bool = False,
        confidence: float = 1.0,
        risk_level_conflict: bool = False,
        missing_information: list[str] | None = None,
    ) -> HumanReviewDecision:
        reasons = []
        if risk_level == "high":
            reasons.append("HIGH_RISK")
        if evidence_conflict:
            reasons.append("EVIDENCE_CONFLICT")
        if insufficient_evidence:
            reasons.append("INSUFFICIENT_EVIDENCE")
        if unsupported_claim:
            reasons.append("UNSUPPORTED_CLAIM")
        if fallback:
            reasons.append("FALLBACK_USED")
        if prompt_injection:
            reasons.append("PROMPT_INJECTION")
        if prohibited_action:
            reasons.append("PROHIBITED_ACTION")
        if schema_repeated_failure:
            reasons.append("SCHEMA_REPEATED_FAILURE")
        if tool_failure:
            reasons.append("TOOL_FAILURE")
        if confidence < 0.65:
            reasons.append("LOW_CONFIDENCE")
        if risk_level_conflict:
            reasons.append("RISK_LEVEL_CONFLICT")
        return HumanReviewDecision(
            review_required=bool(reasons),
            review_reason_codes=reasons,
            evidence_summary="aggregate evidence summary only",
            missing_information=missing_information or [],
            recommended_next_step="manual_review" if reasons else "no_manual_review_required",
        )
