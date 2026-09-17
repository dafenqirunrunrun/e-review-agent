from __future__ import annotations

from app.agent_rag.eligibility import evaluate_evidence_eligibility, filter_eligible_candidates
from app.agent_rag.phase2_retrieval import RetrievalCandidate
from app.agent_rag.reranker import GovernedReranker, RerankerConfig


EVAL_TIME = "2026-07-22T00:00:00Z"


def _row(**overrides):
    data = {
        "tenant_id": "tenant-a",
        "document_id": "doc-1",
        "document_version": "1",
        "chunk_id": "chunk-1",
        "content": "refund after-sales policy evidence",
        "content_hash": "abc123abc123",
        "active": True,
        "deleted": False,
        "visibility": "tenant",
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_to": None,
    }
    data.update(overrides)
    return data


def _candidate(chunk_id: str, **row_overrides) -> RetrievalCandidate:
    row_overrides.setdefault("content_hash", f"{chunk_id}abc123abc123")
    row = _row(chunk_id=chunk_id, **row_overrides)
    return RetrievalCandidate(
        retrieverType="fixture",
        tenantId=str(row["tenant_id"]),
        documentId=str(row["document_id"]),
        chunkId=chunk_id,
        sparseScore=0.5,
        sparseRank=1,
        rawRank=1,
        fusionScore=0.5,
        fusionRank=1,
        row=row,
    )


def test_v22_canonical_expiration_is_right_open_interval():
    assert evaluate_evidence_eligibility(_row(effective_to=None), "tenant-a", EVAL_TIME).reasonCode == "ELIGIBLE"
    assert evaluate_evidence_eligibility(_row(effective_to="2026-07-22T00:00:01Z"), "tenant-a", EVAL_TIME).reasonCode == "ELIGIBLE"
    assert evaluate_evidence_eligibility(_row(effective_to=EVAL_TIME), "tenant-a", EVAL_TIME).reasonCode == "EXPIRED"
    assert evaluate_evidence_eligibility(_row(effective_to="2026-07-21T23:59:59Z"), "tenant-a", EVAL_TIME).reasonCode == "EXPIRED"


def test_v22_canonical_effective_time_boundary_and_timezone_inputs():
    assert evaluate_evidence_eligibility(_row(effective_from=EVAL_TIME), "tenant-a", EVAL_TIME).reasonCode == "ELIGIBLE"
    assert evaluate_evidence_eligibility(_row(effective_from="2026-07-22T08:00:00+08:00"), "tenant-a", EVAL_TIME).reasonCode == "ELIGIBLE"
    assert evaluate_evidence_eligibility(_row(effective_from="2026-07-22T00:00:00.001Z"), "tenant-a", EVAL_TIME).reasonCode == "NOT_YET_EFFECTIVE"


def test_v22_canonical_tenant_public_and_inactive_rejections():
    assert evaluate_evidence_eligibility(_row(tenant_id="tenant-b"), "tenant-a", EVAL_TIME).reasonCode == "TENANT_MISMATCH"
    assert evaluate_evidence_eligibility(_row(tenant_id="__public__", visibility="public"), "tenant-a", EVAL_TIME).reasonCode == "ELIGIBLE"
    assert evaluate_evidence_eligibility(_row(tenant_id="__public__", visibility="tenant"), "tenant-a", EVAL_TIME).reasonCode == "TENANT_SCOPE_INVALID"
    assert evaluate_evidence_eligibility(_row(active=False), "tenant-a", EVAL_TIME).reasonCode == "INACTIVE"
    assert evaluate_evidence_eligibility(_row(disabled=True), "tenant-a", EVAL_TIME).reasonCode == "DISABLED"


def test_v22_filter_rejects_duplicates_without_text_leakage():
    first = _candidate("chunk-a", content_hash="duplicateabc123")
    duplicate = _candidate("chunk-b", content_hash="duplicateabc123")
    accepted, decisions = filter_eligible_candidates([first, duplicate], tenant_id="tenant-a", evaluation_time_utc=EVAL_TIME)
    assert [item.chunkId for item in accepted] == ["chunk-a"]
    assert [decision.reasonCode for decision in decisions] == ["ELIGIBLE", "DUPLICATE"]


def test_v22_reranker_uses_variable_k_without_backfill():
    candidates = [
        _candidate("chunk-good"),
        _candidate("chunk-expired", effective_to=EVAL_TIME),
        _candidate("chunk-future", effective_from="2026-07-22T00:00:01Z"),
    ]
    result = GovernedReranker(RerankerConfig(requested_type="deterministic", final_k=5)).rerank(
        "refund policy",
        candidates,
        top_k=5,
        tenant_id="tenant-a",
        evaluation_time_utc=EVAL_TIME,
    )
    assert [item.chunkId for item in result.candidates] == ["chunk-good"]
    assert result.outputCount == 1
