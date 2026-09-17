"""Versioned, lossless compatibility for persisted review governance snapshots.

Schema migration only changes the representation of a historical result.  It
never runs the current model or rewrites an operator's final decision.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.contracts.review_semantics import (
    FAILURE_REASON_LABELS,
    RISK_TYPE_REGISTRY,
    risk_type_description,
    risk_type_label,
)


GOVERNANCE_SCHEMA_V1 = "review-governance-v1"
GOVERNANCE_SCHEMA_V2 = "review-governance-v2"
CURRENT_GOVERNANCE_SCHEMA_VERSION = GOVERNANCE_SCHEMA_V2
HUMAN_RESOLVED_STATUSES = frozenset({"closed", "ignored", "replied", "transferred", "processed"})

# Only aliases with identical business meaning belong here.  Semantic changes
# such as after_sales_risk -> fake_review require a separately requested
# re-evaluation and must never be inferred by a schema migration.
RISK_TYPE_ALIASES: dict[str, str] = {
    "paid_review_risk": "paid_review",
}


@dataclass(frozen=True)
class GovernanceMigrationResult:
    outcome: str
    snapshot: dict[str, Any]
    changes: list[dict[str, Any]]
    unknown_risk_types: list[str]
    requires_reevaluation: bool


def snapshot_version(snapshot: dict[str, Any] | None) -> str:
    if not isinstance(snapshot, dict):
        return "unknown"
    return str(snapshot.get("governanceSchemaVersion") or snapshot.get("schemaVersion") or GOVERNANCE_SCHEMA_V1)


def migrate_snapshot(
    snapshot: dict[str, Any] | None,
    *,
    review_text: str = "",
    task_status: str = "",
    migrated_at: str | None = None,
) -> GovernanceMigrationResult:
    """Return a v2 snapshot without losing the original historical payload."""
    if not isinstance(snapshot, dict) or not snapshot:
        return GovernanceMigrationResult("unknown", {}, [], [], False)

    source_version = snapshot_version(snapshot)
    if source_version == CURRENT_GOVERNANCE_SCHEMA_VERSION:
        return GovernanceMigrationResult("already_current", deepcopy(snapshot), [], [], bool(snapshot.get("requiresReevaluation")))

    original = deepcopy(snapshot)
    migrated = deepcopy(snapshot)
    changes: list[dict[str, Any]] = []
    raw_risks = _string_list(migrated.get("riskTypes"))
    risks, unknown_risks = _normalize_risk_types(raw_risks, changes)
    if not risks:
        risks = ["normal_review"] if _decision_code(migrated) == "auto_pass" else ["other"]
        changes.append({"field": "riskTypes", "from": raw_risks, "to": risks, "rule": "missing_risk_types"})

    evidence_status = _normalize_evidence_status(migrated.get("evidenceStatus"), migrated, changes)
    failure_reasons = _normalize_failure_reasons(migrated.get("failureReasons"), evidence_status, changes)
    reflection_code = str(migrated.get("reflectionReasonCode") or "")
    if not reflection_code:
        reflection_code = "SUPPORTED" if evidence_status == "supported" else str(failure_reasons[0]["code"])
        changes.append({"field": "reflectionReasonCode", "to": reflection_code, "rule": "derived_from_evidence"})

    coverage = _normalize_coverage(migrated.get("riskCoverage"), risks, evidence_status, changes)
    requires_reevaluation = _requires_reevaluation(original, review_text)
    if requires_reevaluation:
        changes.append({"field": "requiresReevaluation", "to": True, "rule": "historical_risk_conflict"})

    migration_meta = {
        "sourceVersion": source_version,
        "targetVersion": CURRENT_GOVERNANCE_SCHEMA_VERSION,
        "migratedAt": migrated_at or datetime.now(timezone.utc).isoformat(),
        "migrationRule": "governance-schema-v1-to-v2-lossless",
        "originalRiskTypes": raw_risks,
        "originalEvidenceStatus": original.get("evidenceStatus"),
        "humanResolvedAtMigration": str(task_status or "").lower() in HUMAN_RESOLVED_STATUSES,
    }
    migrated["schemaVersion"] = CURRENT_GOVERNANCE_SCHEMA_VERSION
    migrated["governanceSchemaVersion"] = CURRENT_GOVERNANCE_SCHEMA_VERSION
    migrated["riskTypes"] = risks
    migrated["evidenceStatus"] = evidence_status
    migrated["reflectionReasonCode"] = reflection_code
    migrated["failureReasons"] = failure_reasons
    migrated["riskCoverage"] = coverage
    migrated["originalGovernanceSnapshot"] = original
    migrated["migration"] = migration_meta
    migrated["requiresReevaluation"] = requires_reevaluation
    migrated["historyDisplay"] = {
        "isHistorical": True,
        "message": "历史治理快照已按当前展示口径适配。" if not requires_reevaluation else "历史判断与当前规则可能存在差异，需要显式重新评估后才能更新结论。",
    }
    outcome = "requires_reevaluation" if requires_reevaluation else "unknown" if unknown_risks else "migrated"
    return GovernanceMigrationResult(outcome, migrated, changes, unknown_risks, requires_reevaluation)


def adapt_snapshot_for_display(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    """Read-only adapter for v1 rows that have not yet been persisted as v2."""
    if not isinstance(snapshot, dict):
        return snapshot
    if snapshot_version(snapshot) == CURRENT_GOVERNANCE_SCHEMA_VERSION:
        return snapshot
    return migrate_snapshot(snapshot).snapshot


def _normalize_risk_types(values: list[str], changes: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    normalized: list[str] = []
    unknown: list[str] = []
    for value in values:
        target = RISK_TYPE_ALIASES.get(value, value)
        if target != value:
            changes.append({"field": "riskTypes", "from": value, "to": target, "rule": "risk_type_alias"})
        if target not in RISK_TYPE_REGISTRY:
            unknown.append(target)
        if target not in normalized:
            normalized.append(target)
    return normalized, unknown


def _normalize_evidence_status(value: Any, snapshot: dict[str, Any], changes: list[dict[str, Any]]) -> str:
    current = str(value or "").lower()
    if current in {"supported", "insufficient", "mismatch"}:
        return current
    derived = "supported" if snapshot.get("evidenceSufficient") is True or _decision_code(snapshot) == "auto_pass" else "insufficient"
    changes.append({"field": "evidenceStatus", "from": value, "to": derived, "rule": "legacy_evidence_status"})
    return derived


def _normalize_failure_reasons(value: Any, evidence_status: str, changes: list[dict[str, Any]]) -> list[dict[str, str]]:
    reasons = [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []
    normalized = [{"code": str(item.get("code") or "UNKNOWN"), "message": str(item.get("message") or "")} for item in reasons]
    if normalized:
        for item in normalized:
            if not item["message"]:
                item["message"] = FAILURE_REASON_LABELS.get(item["code"], "当前结果需要人工确认。")
        return normalized
    if evidence_status == "supported":
        return []
    code = "TAG_MISMATCH" if evidence_status == "mismatch" else "NO_EVIDENCE"
    changes.append({"field": "failureReasons", "to": [code], "rule": "derived_from_evidence_status"})
    return [{"code": code, "message": FAILURE_REASON_LABELS[code]}]


def _normalize_coverage(value: Any, risks: list[str], evidence_status: str, changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = {str(item.get("riskType")): item for item in value if isinstance(item, dict)} if isinstance(value, list) else {}
    coverage = []
    for risk in risks:
        item = existing.get(risk, {})
        status = str(item.get("status") or ("supported" if evidence_status == "supported" or risk == "normal_review" else "insufficient"))
        coverage.append({
            "riskType": risk,
            "label": str(item.get("label") or risk_type_label(risk)),
            "description": str(item.get("description") or risk_type_description(risk)),
            "status": status,
            "statusText": str(item.get("statusText") or ("已支持" if status == "supported" else "证据不足")),
            "supportedBy": _string_list(item.get("supportedBy")),
            "missingEvidenceTags": _string_list(item.get("missingEvidenceTags")),
        })
    if not isinstance(value, list):
        changes.append({"field": "riskCoverage", "to": "derived", "rule": "missing_risk_coverage"})
    return coverage


def _requires_reevaluation(snapshot: dict[str, Any], review_text: str) -> bool:
    risks = set(_string_list(snapshot.get("riskTypes")))
    if "after_sales_risk" not in risks:
        return False
    text = " ".join([review_text, str(snapshot.get("reflectionReason") or ""), str(snapshot.get("summary") or "")]).lower()
    return any(token in text for token in ("返现", "截图", "五星", "cashback", "paid review", "rating manipulation"))


def _decision_code(snapshot: dict[str, Any]) -> str:
    decision = snapshot.get("decision")
    return str(decision.get("code") or "") if isinstance(decision, dict) else ""


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if value in (None, ""):
        return []
    return [str(value)]
