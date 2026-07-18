from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvidenceVerificationResult:
    verified_evidence: list[str]
    rejected_evidence: list[str]
    unsupported_claims: list[str]
    evidence_coverage: float
    evidence_conflict: bool
    human_review_required: bool
    reason_codes: list[str] = field(default_factory=list)


class EvidenceVerifier:
    def verify(
        self,
        *,
        tenant_id: str,
        chunks: list[dict],
        evidence: list[str],
        claims: list[str],
        risk_level: str,
    ) -> EvidenceVerificationResult:
        active_chunks = [row for row in chunks if row.get("tenant_id") == tenant_id and row.get("active", True) and not row.get("deleted", False)]
        if not active_chunks:
            return EvidenceVerificationResult([], evidence, claims, 0.0, False, True, ["EMPTY_RETRIEVAL"])
        joined = "\n".join(str(row.get("content") or "") for row in active_chunks)
        verified = [item for item in evidence if item and item in joined]
        rejected = [item for item in evidence if item not in verified]
        unsupported = [claim for claim in claims if claim and claim not in joined]
        low_trust_only = all(row.get("trust_level") in {"external_untrusted", "synthetic"} for row in active_chunks)
        conflict = bool(verified and unsupported)
        coverage = len(verified) / max(1, len(evidence))
        reason_codes = []
        if rejected:
            reason_codes.append("EVIDENCE_NOT_FOUND")
        if unsupported:
            reason_codes.append("UNSUPPORTED_CLAIM")
        if low_trust_only and risk_level == "high":
            reason_codes.append("LOW_TRUST_HIGH_RISK")
        human_review_required = bool(reason_codes) or conflict or (coverage < 1.0)
        return EvidenceVerificationResult(verified, rejected, unsupported, coverage, conflict, human_review_required, reason_codes)
