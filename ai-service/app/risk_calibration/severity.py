from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class SeverityRank(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


BASE_SEVERITY: dict[str, SeverityRank] = {
    "normal_review": SeverityRank.LOW,
    "negative_review": SeverityRank.MEDIUM,
    "after_sales_risk": SeverityRank.MEDIUM,
    "rating_conflict": SeverityRank.MEDIUM,
    "low_confidence": SeverityRank.MEDIUM,
    "modality_conflict": SeverityRank.MEDIUM,
    "fake_review_suspected": SeverityRank.MEDIUM,
    "other": SeverityRank.MEDIUM,
    "fake_review": SeverityRank.HIGH,
    "paid_review": SeverityRank.HIGH,
    "rating_manipulation": SeverityRank.HIGH,
    "review_suppression": SeverityRank.HIGH,
    "privacy_risk": SeverityRank.HIGH,
    "harassment_or_abuse": SeverityRank.HIGH,
    "safety_or_fraud_risk": SeverityRank.HIGH,
}


EXPLICIT_INCENTIVE_TERMS = (
    "返现", "红包", "礼金", "现金", "优惠券", "赠品", "cashback", "rebate", "coupon", "payment",
)
ORGANIZED_MANIPULATION_TERMS = (
    "批量", "组织", "统一模板", "集中", "刷单团", "水军", "员工", "亲友", "coordinated", "organized", "bulk accounts",
)
IMMEDIATE_HARM_TERMS = (
    "爆炸", "起火", "中毒", "人身安全", "报复", "上门", "身份证", "住址", "explosion", "poison", "physical harm",
)


@dataclass(frozen=True)
class SeverityAssessment:
    severity: str
    severityReasons: tuple[str, ...]

    def model_dump(self) -> dict[str, object]:
        return {"severity": self.severity, "severityReasons": list(self.severityReasons)}


class RiskSeverityEvaluator:
    """Maps stable risk codes to consequence severity without trusting an LLM label."""

    version = "risk-severity-registry-v1"

    def evaluate(
        self,
        risk_types: list[str],
        *,
        review_text: str = "",
        evidence_status: str = "",
    ) -> SeverityAssessment:
        normalized = sorted(set(risk_types or ["normal_review"]))
        ranked = [(risk, BASE_SEVERITY.get(risk, SeverityRank.MEDIUM)) for risk in normalized]
        rank = max((value for _, value in ranked), default=SeverityRank.LOW)
        reasons = [f"RISK_TYPE_{risk.upper()}" for risk, value in ranked if value == rank]
        lowered = review_text.lower()
        high_count = sum(1 for _, value in ranked if value >= SeverityRank.HIGH)

        if any(term in lowered for term in EXPLICIT_INCENTIVE_TERMS):
            rank = max(rank, SeverityRank.HIGH)
            reasons.append("EXPLICIT_INCENTIVE")
        organized = any(term in lowered for term in ORGANIZED_MANIPULATION_TERMS)
        if organized:
            rank = max(rank, SeverityRank.HIGH)
            reasons.append("ORGANIZED_MANIPULATION")
        if high_count >= 2:
            rank = SeverityRank.CRITICAL
            reasons.append("MULTIPLE_HIGH_RISK_TYPES")
        elif organized and rank >= SeverityRank.HIGH:
            rank = SeverityRank.CRITICAL
            reasons.append("ORGANIZED_HIGH_IMPACT")
        if any(term in lowered for term in IMMEDIATE_HARM_TERMS) and rank >= SeverityRank.HIGH:
            rank = SeverityRank.CRITICAL
            reasons.append("IMMEDIATE_HARM_CONTEXT")
        if evidence_status == "supported" and rank >= SeverityRank.HIGH:
            reasons.append("POLICY_EVIDENCE_SUPPORTED")

        unique_reasons = tuple(dict.fromkeys(reasons))
        return SeverityAssessment(rank.name.lower(), unique_reasons)

    @staticmethod
    def registry() -> dict[str, str]:
        return {risk: severity.name.lower() for risk, severity in sorted(BASE_SEVERITY.items())}
