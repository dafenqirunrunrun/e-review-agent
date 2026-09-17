from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


ELIGIBILITY_VERSION = "agent-rag-v22-canonical-evidence-eligibility-v1"
PUBLIC_TENANT = "__public__"


@dataclass(frozen=True)
class EvidenceEligibilityDecision:
    eligible: bool
    reasonCode: str
    evaluatedAtUtc: str


def evaluate_evidence_eligibility(
    candidate: Any,
    tenant_id: str,
    evaluation_time_utc: str,
    *,
    seen_content_hashes: set[str] | None = None,
) -> EvidenceEligibilityDecision:
    evaluated_at = canonical_utc(evaluation_time_utc)
    row = _row(candidate)
    if not row:
        return _decision(False, "EMPTY_TEXT", evaluated_at)
    text = str(row.get("content") or row.get("text") or "").strip()
    if not text:
        return _decision(False, "EMPTY_TEXT", evaluated_at)

    tenant = str(row.get("tenant_id") or row.get("tenantId") or getattr(candidate, "tenantId", "") or "")
    visibility = str(row.get("visibility") or ("public" if tenant == PUBLIC_TENANT else "tenant"))
    if tenant == PUBLIC_TENANT and visibility != "public":
        return _decision(False, "TENANT_SCOPE_INVALID", evaluated_at)
    if tenant not in {tenant_id, PUBLIC_TENANT}:
        return _decision(False, "TENANT_MISMATCH", evaluated_at)

    if bool(row.get("deleted", False)) or str(row.get("status") or "").lower() == "deleted":
        return _decision(False, "TOMBSTONED", evaluated_at)
    if row.get("active", True) is False or str(row.get("status") or "").lower() in {"inactive", "retired"}:
        return _decision(False, "INACTIVE", evaluated_at)
    if row.get("disabled", False) is True or str(row.get("status") or "").lower() == "disabled":
        return _decision(False, "DISABLED", evaluated_at)

    moment = parse_utc(evaluated_at)
    effective_from = row.get("effective_from") or row.get("effectiveFrom")
    if effective_from and parse_utc(str(effective_from)) > moment:
        return _decision(False, "NOT_YET_EFFECTIVE", evaluated_at)
    expires_at = row.get("expires_at") or row.get("expiresAt") or row.get("effective_to") or row.get("effectiveTo")
    if expires_at and moment >= parse_utc(str(expires_at)):
        return _decision(False, "EXPIRED", evaluated_at)

    version = str(row.get("document_version") or row.get("documentVersion") or "1").strip()
    if not version:
        return _decision(False, "VERSION_INVALID", evaluated_at)
    content_hash = str(row.get("content_hash") or row.get("contentHash") or "").strip()
    if len(content_hash) < 12:
        return _decision(False, "CONTENT_HASH_MISMATCH", evaluated_at)
    if seen_content_hashes is not None and content_hash in seen_content_hashes:
        return _decision(False, "DUPLICATE", evaluated_at)
    return _decision(True, "ELIGIBLE", evaluated_at)


def filter_eligible_candidates(
    candidates: list[Any],
    *,
    tenant_id: str,
    evaluation_time_utc: str,
) -> tuple[list[Any], list[EvidenceEligibilityDecision]]:
    accepted: list[Any] = []
    decisions: list[EvidenceEligibilityDecision] = []
    seen: set[str] = set()
    for candidate in candidates:
        decision = evaluate_evidence_eligibility(
            candidate,
            tenant_id,
            evaluation_time_utc,
            seen_content_hashes=seen,
        )
        decisions.append(decision)
        if decision.eligible:
            seen.add(_content_hash(candidate))
            accepted.append(candidate)
    return accepted, decisions


def canonical_utc(value: str) -> str:
    return parse_utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("EVALUATION_TIME_REQUIRED")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _decision(eligible: bool, reason: str, evaluated_at: str) -> EvidenceEligibilityDecision:
    return EvidenceEligibilityDecision(eligible=eligible, reasonCode=reason, evaluatedAtUtc=evaluated_at)


def _row(candidate: Any) -> dict[str, Any]:
    if isinstance(candidate, dict):
        return candidate
    row = getattr(candidate, "row", None)
    return dict(row or {})


def _content_hash(candidate: Any) -> str:
    row = _row(candidate)
    return str(row.get("content_hash") or row.get("contentHash") or "")
