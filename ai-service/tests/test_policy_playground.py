from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agentic_workflow.workflow import IntentDecision, IntentRouterAgent
from app.api import policy_playground as playground_api
from app.policy_rag.models import PolicySearchResult
from app.policy_rag.playground import PolicyEvidencePlayground, PolicyPlaygroundRequest
from app.policy_rag.reranker import PolicyRerankOutcome
from app.schemas.review import ReviewAnalyzeRequest


def evidence(*, tags: list[str] | None = None, source_url: str = "https://example.org/policy") -> PolicySearchResult:
    return PolicySearchResult(
        evidenceId="E1",
        chunkId="policy-chunk-001",
        sourceType="regulation",
        sourceName="评价治理规范",
        sourceUrl=source_url,
        title="评价真实性",
        snippet="不得通过返现要求消费者发布五星评价。",
        riskTypes=["rating_manipulation"],
        evidenceTags=tags or ["rating_manipulation"],
        score=0.8,
        contentHash="abcdef1234567890",
        sectionPath=["评价规则", "利益诱导"],
        clauseId="4.2",
        retrievalMode="hybrid_bm25_qwen_faiss_rrf",
        retrieval={"mode": "hybrid", "score": 0.8},
    )


class StubRouter:
    def __init__(self, decision: IntentDecision):
        self.decision = decision

    def route(self, _payload):
        return self.decision


class StubRetriever:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0
        self.last_dense_error = ""

    def search(self, *_args, **_kwargs):
        self.calls += 1
        return list(self.rows)

    def chunk_for_id(self, _chunk_id):
        return None

    def readiness(self):
        return {"chunkCount": len(self.rows)}

    def observability_metadata(self):
        return {"policyIndexVersion": "test-index-version"}


class StubReranker:
    enabled = False
    candidate_k = 5

    def rerank(self, _query, candidates, **_kwargs):
        return PolicyRerankOutcome(
            evidence=list(candidates),
            ranked_candidates=list(candidates),
            metadata={"status": "disabled", "effectiveMode": "rrf", "fallbackUsed": False},
        )


def service(decision: IntentDecision, rows) -> tuple[PolicyEvidencePlayground, StubRetriever]:
    retriever = StubRetriever(rows)
    return PolicyEvidencePlayground(
        retriever=retriever,
        router=StubRouter(decision),
        reranker=StubReranker(),
    ), retriever


def test_supported_query_returns_bounded_traceable_evidence():
    playground, retriever = service(
        IntentDecision("governance_required", "rating_manipulation", ["rating_manipulation"], ["RISK"], 0.9, True),
        [evidence(), evidence()],
    )
    result = playground.query(PolicyPlaygroundRequest(query="五星好评截图后返现", topK=3))

    assert result["isolated"] is True
    assert result["evidenceStatus"] == "supported"
    assert result["evidence"][0]["sourceUrl"].startswith("https://")
    assert result["evidence"][0]["sectionPath"] == ["评价规则", "利益诱导"]
    assert len(result["evidence"]) == 1
    assert retriever.calls == 1


def test_normal_query_does_not_execute_retrieval_or_show_empty_policy_cards():
    playground, retriever = service(
        IntentDecision("low_touch", "normal_feedback", [], ["NO_RISK_SIGNAL"], 0.9, False),
        [evidence()],
    )
    result = playground.query(PolicyPlaygroundRequest(query="商品很好，物流也很快"))

    assert result["decision"]["code"] == "normal_review"
    assert result["evidenceStatus"] == "not_required"
    assert result["evidence"] == []
    assert result["technical"]["fastEligibility"]["executedChain"] == "FAST_SHORT_CHAIN"
    assert retriever.calls == 0


@pytest.mark.parametrize("query", ["你好", "你好啊", "您好呀！", "在吗？", "你是谁", "🙂🙂"])
def test_greeting_returns_guidance_without_running_router_or_retrieval(query):
    playground, retriever = service(
        IntentDecision("governance_required", "fake_review", ["fake_review"], ["RISK"], 0.9, True),
        [evidence()],
    )

    result = playground.query(PolicyPlaygroundRequest(query=query))

    assert result["route"] == "input_guidance"
    assert result["decision"]["code"] == "input_guidance"
    assert result["evidenceStatus"] == "not_required"
    assert result["technical"]["actualMode"] == "not_executed"
    assert result["evidence"] == []
    assert retriever.calls == 0


def test_empty_or_mismatched_evidence_never_becomes_supported():
    decision = IntentDecision("governance_required", "review_suppression", ["review_suppression"], ["RISK"], 0.9, True)
    empty, _ = service(decision, [])
    mismatch, _ = service(decision, [evidence(tags=["rating_manipulation"])])

    empty_result = empty.query(PolicyPlaygroundRequest(query="删掉差评才能退款"))
    mismatch_result = mismatch.query(PolicyPlaygroundRequest(query="删掉差评才能退款"))

    assert empty_result["evidenceStatus"] == "insufficient"
    assert empty_result["requiresHumanReview"] is True
    assert mismatch_result["evidenceStatus"] in {"insufficient", "mismatch"}
    assert mismatch_result["decision"]["code"] == "manual_review"


def test_http_contract_rejects_extra_fields_and_returns_service_result(monkeypatch):
    playground, _ = service(
        IntentDecision("low_touch", "normal_feedback", [], ["NO_RISK_SIGNAL"], 0.9, False),
        [],
    )
    monkeypatch.setattr(playground_api, "playground", playground)
    app = FastAPI()
    app.include_router(playground_api.router, prefix="/api/v1")
    client = TestClient(app)

    response = client.post("/api/v1/policy/playground/query", json={"query": "商品很好，物流也很快"})
    invalid = client.post("/api/v1/policy/playground/query", json={"query": "正常评论", "unknown": True})

    assert response.status_code == 200
    assert response.json()["isolated"] is True
    assert invalid.status_code == 422


def test_uncertain_low_touch_query_fails_closed_to_long_chain():
    playground, retriever = service(
        IntentDecision("low_touch", "normal_feedback", [], ["NO_RISK_SIGNAL"], 0.8, False),
        [],
    )

    result = playground.query(PolicyPlaygroundRequest(query="这个东西感觉有点奇怪"))

    assert result["route"] == "governance_required"
    assert result["decision"]["code"] == "manual_review"
    assert result["evidenceStatus"] == "insufficient"
    assert result["riskTypes"] == ["low_confidence"]
    assert result["technical"]["fastEligibility"]["executedChain"] == "LONG_ANALYSIS_CHAIN"
    assert retriever.calls == 1


def test_low_confidence_cannot_be_promoted_by_unrelated_policy_evidence():
    playground, _ = service(
        IntentDecision("low_touch", "normal_feedback", [], ["NO_RISK_SIGNAL"], 0.8, False),
        [evidence(tags=["low_confidence"])],
    )

    result = playground.query(PolicyPlaygroundRequest(query="这个东西感觉有点奇怪"))

    assert result["evidenceStatus"] == "insufficient"
    assert result["requiresHumanReview"] is True
    assert result["decision"]["code"] == "manual_review"
    assert "LOW_CONFIDENCE" in result["reasonCodes"]


def test_colloquial_delete_review_phrase_enters_strict_route():
    router = IntentRouterAgent(rule_enhancements_enabled=True, safety_gate_enabled=True)
    payload = ReviewAnalyzeRequest(
        reviewId="playground-router-test",
        productId="test",
        productName="test",
        reviewText="客服说先把差评删掉，才给我办理退款。",
        rating=None,
        ratingSource="UNKNOWN",
    )

    decision = router._route_with_rules(payload)

    assert decision.route == "governance_required"
    assert "review_suppression" in decision.risk_hints
    assert "after_sales_risk" in decision.risk_hints


def test_candidate_target_uses_only_verified_managed_staging_index(tmp_path, monkeypatch):
    version = "policy-20260916T213237-0963c90a"
    directory = tmp_path / "versions" / f"{version}.staging"
    directory.mkdir(parents=True)
    (directory / "policy_chunks.jsonl").write_text("", encoding="utf-8")
    (directory / "release_manifest.json").write_text(json.dumps({
        "version": version,
        "releaseEvaluation": {"schemaVersion": "policy-release-evaluation-v1"},
    }), encoding="utf-8")
    monkeypatch.setenv("E_REVIEW_POLICY_RAG_MANAGED_INDEX_ROOT", str(tmp_path))
    current = StubRetriever([])
    candidate = StubRetriever([evidence()])
    monkeypatch.setattr("app.policy_rag.playground.PolicyEvidenceRetriever.from_jsonl", lambda *_args, **_kwargs: candidate)
    playground = PolicyEvidencePlayground(
        retriever=current,
        router=StubRouter(IntentDecision("governance_required", "rating_manipulation", ["rating_manipulation"], ["RISK"], 0.9, True)),
        reranker=StubReranker(),
    )

    result = playground.query(PolicyPlaygroundRequest(
        query="五星评价截图返现",
        indexTarget="candidate",
        candidateVersion=version,
    ))

    assert current.calls == 0
    assert candidate.calls == 1
    assert result["technical"]["indexTarget"] == "candidate"
    assert result["technical"]["requestedIndexVersion"] == version
    assert result["evidenceStatus"] == "supported"


def test_candidate_target_rejects_untrusted_version_value():
    with pytest.raises(ValueError):
        PolicyPlaygroundRequest(query="test", indexTarget="candidate", candidateVersion="../../outside")


def test_published_or_superseded_version_remains_available_for_read_only_comparison(tmp_path, monkeypatch):
    version = "policy-20260916T213237-0963c90a"
    directory = tmp_path / "versions" / version
    directory.mkdir(parents=True)
    (directory / "policy_chunks.jsonl").write_text("", encoding="utf-8")
    (directory / "release_manifest.json").write_text(json.dumps({
        "version": version,
        "releaseEvaluation": {"schemaVersion": "policy-release-evaluation-v1", "gatePassed": True},
    }), encoding="utf-8")
    monkeypatch.setenv("E_REVIEW_POLICY_RAG_MANAGED_INDEX_ROOT", str(tmp_path))

    assert PolicyEvidencePlayground._candidate_directory(version) == directory.resolve()
