from __future__ import annotations

from typing import Any

from app.contracts.review_semantics import evidence_tag_label, failure_reason_message, risk_type_label
from app.policy_rag.evidence_semantics import RISK_TO_REQUIRED_TAGS, evidence_supports_risk, required_evidence_tags
from app.policy_rag.models import PolicySearchResult, ReflectionDecision


class PolicyReflectionEngine:
    def __init__(self, *, low_confidence_threshold: float = 0.65, high_risk_min_evidence: int = 1):
        self.low_confidence_threshold = low_confidence_threshold
        self.high_risk_min_evidence = high_risk_min_evidence

    def reflect(
        self,
        *,
        risk_level: str,
        risk_types: list[str],
        confidence: float,
        policy_evidence: list[PolicySearchResult | dict[str, Any]],
        action: str = "none",
        retrieval_error: str = "",
    ) -> ReflectionDecision:
        evidence = [item if isinstance(item, PolicySearchResult) else PolicySearchResult.model_validate(item) for item in policy_evidence]
        reasons: list[str] = []
        citation_errors = self._citation_errors(evidence)
        non_policy_uncertainty = {"low_confidence"}
        supported = [
            risk
            for risk in risk_types
            if risk not in non_policy_uncertainty and self._supported(risk, evidence)
        ]
        unsupported = [
            risk
            for risk in risk_types
            if (risk in RISK_TO_REQUIRED_TAGS or risk in non_policy_uncertainty) and risk not in supported
        ]
        risk_coverage = self._risk_coverage(risk_types, evidence, supported)
        if not evidence:
            reasons.append("RETRIEVAL_FAILED" if retrieval_error else "NO_EVIDENCE")
        if risk_level == "high" and len(evidence) < self.high_risk_min_evidence:
            reasons.append("NO_EVIDENCE")
        if citation_errors:
            reasons.extend(self._citation_reason_codes(citation_errors))
        if confidence < self.low_confidence_threshold or non_policy_uncertainty.intersection(risk_types):
            reasons.append("LOW_CONFIDENCE")
        if action in {"refund", "delete_review", "ban_user", "compensate", "ship_order"}:
            reasons.append("UNSUPPORTED_ACTION")
        if unsupported:
            reasons.append("PARTIAL_RISK_COVERAGE" if supported else "TAG_MISMATCH")
        passed = not reasons
        evidence_status = self._status(evidence, unsupported, citation_errors)
        reason_codes = sorted(set(reasons))
        return ReflectionDecision(
            passed=passed,
            evidenceStatus=evidence_status,
            reasonCodes=reason_codes,
            summary=self._summary(evidence_status, citation_errors, unsupported, risk_types, retrieval_error),
            technicalSummary=self._technical_summary(evidence_status, citation_errors, unsupported, retrieval_error),
            primaryReasonCode=reason_codes[0] if reason_codes else "SUPPORTED",
            failureReasons=self._failure_reasons(reason_codes, unsupported, citation_errors, retrieval_error),
            riskCoverage=risk_coverage,
            supportedRiskTypes=sorted(set(supported)),
            unsupportedRiskTypes=sorted(set(unsupported)),
            citationValidationErrors=citation_errors,
            requiresHumanReview=not passed,
            replanHints={} if passed else {
                "forceRetrieval": True,
                "increaseTopK": True,
                "focusRiskTypes": unsupported or risk_types,
                "allowDowngrade": True,
            },
        )

    @staticmethod
    def _supported(risk_type: str, evidence: list[PolicySearchResult]) -> bool:
        return any(evidence_supports_risk(risk_type, item) for item in evidence)

    @staticmethod
    def _citation_errors(evidence: list[PolicySearchResult]) -> list[str]:
        errors: list[str] = []
        valid_sources = {"regulation", "law", "platform_policy", "case", "policy"}
        for index, item in enumerate(evidence, start=1):
            prefix = item.evidenceId or f"E{index}"
            missing = []
            if not item.sourceName:
                missing.append("sourceName")
            if not item.sourceUrl.startswith("http"):
                missing.append("sourceUrl")
            if not item.sectionPath:
                missing.append("sectionPath")
            if not item.contentHash:
                missing.append("contentHash")
            if not item.snippet:
                missing.append("snippet")
            if missing:
                errors.append(f"{prefix}:MISSING_" + ",".join(missing))
            if item.sourceType not in valid_sources:
                errors.append(f"{prefix}:INVALID_SOURCE_TYPE")
        return errors

    @staticmethod
    def _status(evidence: list[PolicySearchResult], unsupported: list[str], citation_errors: list[str]) -> str:
        if not evidence or citation_errors:
            return "insufficient"
        if unsupported:
            return "mismatch"
        return "supported"

    @staticmethod
    def _summary(
        status: str,
        citation_errors: list[str],
        unsupported: list[str],
        risk_types: list[str],
        retrieval_error: str,
    ) -> str:
        if status == "supported":
            return "当前政策依据能够支持该风险判断。"
        if retrieval_error:
            return "政策依据检索暂时失败，当前缺少可验证政策依据，建议人工复核。"
        if citation_errors:
            return "已召回政策依据，但引用来源、条款路径或内容哈希不完整，需要人工确认。"
        if unsupported:
            missing = "、".join(risk_type_label(risk) for risk in unsupported)
            covered = max(0, len(risk_types) - len(unsupported))
            return f"检测到 {len(risk_types)} 类风险，其中 {len(unsupported)} 类缺少对应政策依据：{missing}。已支持 {covered} 类，建议人工确认。"
        return "当前风险未召回可用政策依据，不允许生成自动强处置建议。"

    @staticmethod
    def _technical_summary(status: str, citation_errors: list[str], unsupported: list[str], retrieval_error: str) -> str:
        parts = [f"evidenceStatus={status}"]
        if unsupported:
            parts.append("unsupportedRiskTypes=" + ",".join(unsupported))
        if citation_errors:
            parts.append("citationErrors=" + "|".join(citation_errors))
        if retrieval_error:
            parts.append("retrievalError=" + retrieval_error)
        return "; ".join(parts)

    @staticmethod
    def _citation_reason_codes(citation_errors: list[str]) -> list[str]:
        codes = []
        if any("INVALID_SOURCE_TYPE" in error for error in citation_errors):
            codes.append("SOURCE_INVALID")
        if any("MISSING_" in error for error in citation_errors):
            codes.append("CITATION_INCOMPLETE")
        return codes or ["CITATION_INCOMPLETE"]

    @staticmethod
    def _failure_reasons(
        reason_codes: list[str],
        unsupported: list[str],
        citation_errors: list[str],
        retrieval_error: str,
    ) -> list[dict[str, Any]]:
        rows = []
        for code in reason_codes:
            detail = failure_reason_message(code)
            if code in {"PARTIAL_RISK_COVERAGE", "TAG_MISMATCH"} and unsupported:
                detail = detail + " 缺少依据：" + "、".join(risk_type_label(risk) for risk in unsupported) + "。"
            if code in {"CITATION_INCOMPLETE", "SOURCE_INVALID"} and citation_errors:
                detail = detail + " 异常项：" + "；".join(citation_errors[:3]) + "。"
            if code == "RETRIEVAL_FAILED" and retrieval_error:
                detail = detail + " 系统已保留为人工复核，不会生成伪造引用。"
            rows.append({"code": code, "message": detail})
        return rows

    @staticmethod
    def _risk_coverage(
        risk_types: list[str],
        evidence: list[PolicySearchResult],
        supported: list[str],
    ) -> list[dict[str, Any]]:
        supported_set = set(supported)
        rows = []
        for risk in risk_types:
            required = required_evidence_tags(risk)
            matched = []
            for item in evidence:
                observed = set(item.evidenceTags) | set(item.riskTypes)
                if observed.intersection(required):
                    matched.append(item.evidenceId)
            rows.append(
                {
                    "riskType": risk,
                    "label": risk_type_label(risk),
                    "status": "supported" if risk in supported_set else "insufficient",
                    "statusText": "已支持" if risk in supported_set else "证据不足",
                    "supportedBy": matched[:3],
                    "missingEvidenceTags": [] if matched else [evidence_tag_label(tag) for tag in sorted(required)],
                }
            )
        return rows
