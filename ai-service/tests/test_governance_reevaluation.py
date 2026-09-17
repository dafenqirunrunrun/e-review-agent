from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

from app.services.governance_reevaluation import GovernanceReevaluationService, governance_diff


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "governance_reevaluation_rows.json"


def _snapshot(risks, status="supported", decision="suggest_action", human=False, mode="bm25_fallback"):
    return {
        "schemaVersion": "review-governance-v2", "governanceSchemaVersion": "review-governance-v2",
        "riskTypes": risks, "evidenceStatus": status, "requiresHumanReview": human,
        "decision": {"code": decision}, "humanReview": {"required": human},
        "evidenceCitations": [{"id": "E1", "sourceUrl": "https://example.test/policy", "contentHash": "sha256:e1", "retrieval": {"mode": mode}}],
    }


def _candidate(snapshot):
    result = deepcopy(snapshot)
    result["requiresReevaluation"] = True
    return result


def _row(status="pending", text="五星截图返现，晒图后返10元。"):
    return {"reviewId": "r1", "productId": "p1", "productName": "Demo", "reviewText": text, "rating": 5, "status": status}


def test_non_candidate_is_skipped_without_evaluation():
    service = GovernanceReevaluationService(lambda payload: (_ for _ in ()).throw(AssertionError("must not run")))

    result = service.reevaluate(_snapshot(["normal_review"], decision="auto_pass"), _row())

    assert result.outcome == "skipped"


def test_cashback_semantic_drift_is_material_and_pending_task_needs_attention():
    old = _candidate(_snapshot(["after_sales_risk", "rating_manipulation"], "mismatch", "manual_review", True))
    current = _snapshot(["fake_review", "rating_manipulation"], "supported", "suggest_action", False)

    result = GovernanceReevaluationService(lambda payload: current).reevaluate(old, _row(), policy_index_version="policy-v1", now="2026-09-07T00:00:00Z")

    assert result.outcome == "evaluated"
    assert result.diff["changeSeverity"] == "MATERIAL"
    assert result.diff["addedRiskTypes"] == ["fake_review"]
    assert result.diff["removedRiskTypes"] == ["after_sales_risk"]
    assert result.snapshot["needsHumanAttention"] is True
    assert result.snapshot["reevaluationHistory"][0]["retrievalMode"] == "bm25_fallback"
    assert result.snapshot["reevaluationHistory"][0]["oldGovernanceSnapshot"] == old


def test_closed_task_keeps_human_outcome_and_only_marks_historical_drift():
    old = _candidate(_snapshot(["after_sales_risk"], "mismatch", "manual_review", True))
    row = _row(status="closed")
    row.update({"handler": "operator-a", "handleNote": "人工改判：无需处置"})

    result = GovernanceReevaluationService(lambda payload: _snapshot(["fake_review"], "supported", "suggest_action")).reevaluate(old, row, policy_index_version="policy-v1")

    assert result.snapshot["historicalDecisionDrift"] is True
    assert "needsHumanAttention" not in result.snapshot
    assert row["status"] == "closed"
    assert row["handler"] == "operator-a"
    assert row["handleNote"] == "人工改判：无需处置"


def test_same_signature_is_idempotent_and_policy_version_creates_next_revision():
    old = _candidate(_snapshot(["after_sales_risk"], "mismatch", "manual_review", True))
    service = GovernanceReevaluationService(lambda payload: _snapshot(["fake_review"], "supported", "suggest_action"))

    first = service.reevaluate(old, _row(), policy_index_version="policy-v1")
    repeated = service.reevaluate(first.snapshot, _row(), policy_index_version="policy-v1")
    revised = service.reevaluate(first.snapshot, _row(), policy_index_version="policy-v2")

    assert first.snapshot["reevaluationHistory"][0]["revision"] == "r1"
    assert repeated.outcome == "already_reevaluated"
    assert revised.snapshot["reevaluationHistory"][-1]["revision"] == "r2"


def test_workflow_failure_keeps_original_snapshot_unchanged():
    old = _candidate(_snapshot(["after_sales_risk"], "mismatch", "manual_review", True))
    result = GovernanceReevaluationService(lambda payload: (_ for _ in ()).throw(RuntimeError("retrieval unavailable"))).reevaluate(old, _row())

    assert result.outcome == "failed"
    assert result.snapshot == old
    assert "reevaluationHistory" not in result.snapshot


def test_unchanged_and_fallback_diff_contract():
    old = _candidate(_snapshot(["normal_review"], "supported", "auto_pass", False))
    result = GovernanceReevaluationService(lambda payload: _snapshot(["normal_review"], "supported", "auto_pass", False, "bm25_fallback")).reevaluate(old, _row(text="普通评价。"))

    assert result.diff["changeSeverity"] == "NONE"
    assert result.snapshot["reevaluationHistory"][0]["retrievalMode"] == "bm25_fallback"
    assert governance_diff(old, old)["riskTypesChanged"] is False


def test_current_workflow_really_reevaluates_cashback_to_v2(monkeypatch):
    monkeypatch.setenv("E_REVIEW_AGENTIC_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("E_REVIEW_POLICY_RAG_INDEX_PATH", "data/policy_rag_real/index/policy_chunks.jsonl")
    old = _candidate(_snapshot(["after_sales_risk", "rating_manipulation"], "mismatch", "manual_review", True))

    result = GovernanceReevaluationService().reevaluate(old, _row(), policy_index_version="real-index")

    new = result.snapshot["reevaluationHistory"][0]["reevaluationSnapshot"]
    assert result.diff["changeSeverity"] == "MATERIAL"
    assert new["governanceSchemaVersion"] == "review-governance-v2"
    assert "fake_review" in new["riskTypes"]
    assert new["evidenceStatus"] == "supported"


def test_script_uses_only_marked_fixture_candidates():
    spec = importlib.util.spec_from_file_location("reevaluation_script", ROOT / "scripts" / "reevaluate_review_governance_history.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    args = type("Args", (), {"reason": "SEMANTIC_DRIFT"})()
    deterministic = GovernanceReevaluationService(
        lambda payload: _snapshot(["normal_review"], "supported", "auto_pass", False)
        if payload.review_text == "普通评价。"
        else _snapshot(["fake_review", "rating_manipulation"], "supported", "suggest_action")
    )

    report = module._report(rows, args, deterministic)

    assert report["totalCandidates"] == 3
    assert report["evaluated"] == 3
    assert report["materialChanged"] == 2
    assert report["humanResolvedProtected"] == 1
    assert report["needsHumanAttention"] == 1
