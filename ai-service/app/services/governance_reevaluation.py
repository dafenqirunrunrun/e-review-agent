"""Explicit, append-only re-evaluation of selected historical governance rows."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.agentic_workflow.workflow import AgenticReviewWorkflow
from app.contracts.review_governance import attach_review_governance
from app.core.config import settings
from app.llm.service import LlmReviewService
from app.schemas.review import ReviewAnalyzeRequest, ReviewAnalyzeResponse
from app.services.mock_analyzer import MockAnalyzer
from app.services.rule_agent import RuleAgentWorkflow


WORKFLOW_VERSION = "agentic-review-workflow-v2"
DEFAULT_REASON_CODE = "SEMANTIC_DRIFT"
TERMINAL_TASK_STATUSES = frozenset({"closed", "ignored", "replied", "transferred", "processed"})


@dataclass(frozen=True)
class ReevaluationResult:
    outcome: str
    snapshot: dict[str, Any]
    diff: dict[str, Any] | None = None
    error: str = ""


class GovernanceReevaluationService:
    def __init__(self, evaluate: Callable[[ReviewAnalyzeRequest], dict[str, Any]] | None = None):
        self._evaluate = evaluate or self._evaluate_current_workflow

    def reevaluate(
        self,
        snapshot: dict[str, Any],
        row: dict[str, Any],
        *,
        reason_code: str = DEFAULT_REASON_CODE,
        policy_index_version: str | None = None,
        now: str | None = None,
    ) -> ReevaluationResult:
        if not isinstance(snapshot, dict) or snapshot.get("requiresReevaluation") is not True:
            return ReevaluationResult("skipped", deepcopy(snapshot) if isinstance(snapshot, dict) else {})
        reason = str(reason_code or DEFAULT_REASON_CODE).upper()
        policy_version = policy_index_version or current_policy_index_version()
        signature = _signature(reason, WORKFLOW_VERSION, policy_version)
        existing = _history(snapshot)
        if any(item.get("signature") == signature for item in existing):
            return ReevaluationResult("already_reevaluated", deepcopy(snapshot))

        original = deepcopy(snapshot)
        try:
            current = self._evaluate(_payload(row))
        except Exception as exc:
            return ReevaluationResult("failed", original, error=str(exc)[:160])
        if not isinstance(current, dict) or not current:
            return ReevaluationResult("failed", original, error="CURRENT_WORKFLOW_EMPTY_RESULT")

        diff = governance_diff(original, current)
        terminal = str(row.get("status") or "").lower() in TERMINAL_TASK_STATUSES
        entry = {
            "revision": "r" + str(len(existing) + 1),
            "signature": signature,
            "reevaluatedAt": now or datetime.now(timezone.utc).isoformat(),
            "reevaluationReasonCode": reason,
            "workflowVersion": WORKFLOW_VERSION,
            "policyIndexVersion": policy_version,
            "retrievalMode": _retrieval_mode(current),
            "oldGovernanceSnapshot": original,
            "reevaluationSnapshot": current,
            "oldEvidenceSnapshotRef": evidence_snapshot_reference(original),
            "newEvidenceSnapshotRef": evidence_snapshot_reference(current),
            "diff": diff,
        }
        updated = deepcopy(original)
        updated["reevaluationHistory"] = existing + [entry]
        updated["lastReevaluation"] = {key: entry[key] for key in ("revision", "reevaluatedAt", "reevaluationReasonCode", "workflowVersion", "policyIndexVersion", "retrievalMode", "diff")}
        if diff["changeSeverity"] == "MATERIAL":
            if terminal:
                updated["historicalDecisionDrift"] = True
            else:
                updated["needsHumanAttention"] = True
        return ReevaluationResult("evaluated", updated, diff)

    @staticmethod
    def _evaluate_current_workflow(payload: ReviewAnalyzeRequest) -> dict[str, Any]:
        analyzer = MockAnalyzer()
        workflow = AgenticReviewWorkflow(analyzer=analyzer)
        response: ReviewAnalyzeResponse = LlmReviewService(RuleAgentWorkflow(analyzer=analyzer)).enhance(payload, workflow.analyze(payload))
        return attach_review_governance(payload, response).review_governance.model_dump()


def governance_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_risks, new_risks = _strings(old.get("riskTypes")), _strings(new.get("riskTypes"))
    old_decision, new_decision = _decision(old), _decision(new)
    old_human, new_human = _human_required(old), _human_required(new)
    risks_changed = set(old_risks) != set(new_risks)
    evidence_changed = str(old.get("evidenceStatus") or "") != str(new.get("evidenceStatus") or "")
    decision_changed = old_decision != new_decision
    human_changed = old_human != new_human
    severity = "MATERIAL" if risks_changed or decision_changed or human_changed or (evidence_changed and {old.get("evidenceStatus"), new.get("evidenceStatus")} == {"mismatch", "supported"}) else "MINOR" if evidence_changed else "NONE"
    return {
        "riskTypesChanged": risks_changed,
        "addedRiskTypes": [risk for risk in new_risks if risk not in old_risks],
        "removedRiskTypes": [risk for risk in old_risks if risk not in new_risks],
        "evidenceStatusChanged": evidence_changed,
        "decisionChanged": decision_changed,
        "humanReviewRequirementChanged": human_changed,
        "old": {"riskTypes": old_risks, "evidenceStatus": old.get("evidenceStatus"), "decision": old_decision, "requiresHumanReview": old_human},
        "new": {"riskTypes": new_risks, "evidenceStatus": new.get("evidenceStatus"), "decision": new_decision, "requiresHumanReview": new_human},
        "changeSeverity": severity,
    }


def evidence_snapshot_reference(snapshot: dict[str, Any]) -> str:
    citations = snapshot.get("evidenceCitations") if isinstance(snapshot.get("evidenceCitations"), list) else []
    material = [{"id": item.get("id"), "source": item.get("sourceUrl"), "hash": item.get("contentHash")} for item in citations if isinstance(item, dict)]
    return "sha256:" + hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()


def current_policy_index_version() -> str:
    path = Path(settings.policy_rag.index_path)
    manifest_path = path.parent / "policy_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return str(manifest.get("indexHash") or manifest.get("schemaVersion") or "policy-index-unknown")
    except Exception:
        return "policy-index-unavailable"


def _payload(row: dict[str, Any]) -> ReviewAnalyzeRequest:
    return ReviewAnalyzeRequest(
        review_id=str(row.get("reviewId") or ""), product_id=str(row.get("productId") or "historical"),
        product_name=str(row.get("productName") or "历史评论商品"), review_text=str(row.get("reviewText") or ""),
        image_urls=_strings(row.get("imageUrls")), rating=_integer(row.get("rating")),
    )


def _signature(reason: str, workflow_version: str, policy_version: str) -> str:
    return "sha256:" + hashlib.sha256("|".join([reason, workflow_version, policy_version]).encode("utf-8")).hexdigest()


def _history(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [deepcopy(item) for item in snapshot.get("reevaluationHistory") or [] if isinstance(item, dict)]


def _retrieval_mode(snapshot: dict[str, Any]) -> str:
    citations = snapshot.get("evidenceCitations") or []
    for item in citations:
        if isinstance(item, dict) and isinstance(item.get("retrieval"), dict):
            return str(item["retrieval"].get("mode") or "unknown")
    return "none"


def _decision(snapshot: dict[str, Any]) -> str:
    value = snapshot.get("decision") if isinstance(snapshot.get("decision"), dict) else {}
    return str(value.get("code") or "")


def _human_required(snapshot: dict[str, Any]) -> bool:
    human = snapshot.get("humanReview") if isinstance(snapshot.get("humanReview"), dict) else {}
    return bool(snapshot.get("requiresHumanReview") or human.get("required") or _decision(snapshot) == "manual_review")


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    return [] if value in (None, "") else [str(value)]


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
