from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from app.risk_calibration.calibrator import load_calibrator
from app.risk_calibration.severity import RiskSeverityEvaluator


DEFAULT_CALIBRATOR = Path(__file__).resolve().parents[2] / "data" / "risk_calibration" / "confidence_calibrator_v1.json"


class SmallModelRiskAssessment(BaseModel):
    schemaVersion: str = "small-model-risk-assessment-v1"
    modelProvider: str
    riskTypes: list[str] = Field(default_factory=list)
    rawConfidence: float = Field(ge=0.0, le=1.0)
    calibratedConfidence: float = Field(ge=0.0, le=1.0)
    calibratorVersion: str
    confidenceBucket: str
    complexity: str
    ambiguityFlags: list[str] = Field(default_factory=list)
    severity: str
    severityReasons: list[str] = Field(default_factory=list)
    escalationCandidate: bool
    routingRecommendation: str
    safetyGateTriggered: bool
    safetyGateOverride: bool


class SmallModelRiskAssessor:
    """Produces bounded router features; it never changes the governance decision."""

    def __init__(self, calibrator_path: str | Path | None = None):
        path = calibrator_path or os.getenv("E_REVIEW_CONFIDENCE_CALIBRATOR_PATH") or DEFAULT_CALIBRATOR
        self.calibrator = load_calibrator(path)
        self.severity = RiskSeverityEvaluator()

    def assess(
        self,
        *,
        risk_types: list[str],
        raw_confidence: float,
        reason_codes: list[str],
        review_text: str,
        evidence_status: str = "",
        model_provider: str = "intent-router-rule-v2",
    ) -> SmallModelRiskAssessment:
        risks = sorted(set(risk_types or ["normal_review"]))
        raw = min(1.0, max(0.0, float(raw_confidence)))
        calibrated = self.calibrator.predict(raw) if self.calibrator else raw
        calibrated = min(1.0, max(0.0, calibrated))
        safety_triggered = "HIGH_RISK_SAFETY_GATE" in set(reason_codes)
        flags: list[str] = []
        if raw < 0.65:
            flags.append("LOW_RAW_CONFIDENCE")
        if len(risks) > 1:
            flags.append("MULTI_RISK")
        if len(review_text.strip()) < 8:
            flags.append("SHORT_INPUT")
        if "normal_review" in risks and len(risks) > 1:
            flags.append("CONFLICTING_RISK_LABELS")
        severity = self.severity.evaluate(risks, review_text=review_text, evidence_status=evidence_status)
        complexity = "high" if len(flags) >= 2 or severity.severity == "critical" else "medium" if flags or severity.severity in {"medium", "high"} else "low"
        recommendation = self._recommend(severity.severity, calibrated)
        override = safety_triggered and recommendation == "local_ok"
        if override:
            recommendation = "strict_governance"
        return SmallModelRiskAssessment(
            modelProvider=model_provider,
            riskTypes=risks,
            rawConfidence=round(raw, 6),
            calibratedConfidence=round(calibrated, 6),
            calibratorVersion=self.calibrator.version if self.calibrator else "unfitted-identity",
            confidenceBucket=self._bucket(calibrated),
            complexity=complexity,
            ambiguityFlags=flags,
            severity=severity.severity,
            severityReasons=list(severity.severityReasons),
            escalationCandidate=recommendation in {"escalate_flash", "escalate_pro_candidate", "human_required_candidate"},
            routingRecommendation=recommendation,
            safetyGateTriggered=safety_triggered,
            safetyGateOverride=override,
        )

    @staticmethod
    def _recommend(severity: str, confidence: float) -> str:
        if severity == "critical":
            return "human_required_candidate"
        if severity == "high":
            return "strict_governance" if confidence >= 0.7 else "escalate_pro_candidate"
        if severity == "medium":
            return "local_or_flash" if confidence >= 0.7 else "escalate_flash"
        return "local_ok" if confidence >= 0.7 else "escalate_flash"

    @staticmethod
    def _bucket(confidence: float) -> str:
        index = min(9, int(confidence * 10))
        return f"{index / 10:.1f}-{(index + 1) / 10:.1f}"
