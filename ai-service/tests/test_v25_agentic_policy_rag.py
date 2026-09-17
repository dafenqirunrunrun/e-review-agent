from fastapi.testclient import TestClient

from app.agentic_workflow.workflow import AgenticReviewWorkflow, IntentRouterAgent
from app.contracts.review_governance import attach_review_governance
from app.main import app
from app.policy_rag.chunker import PolicyStructureChunker
from app.policy_rag.index_store import build_policy_index
from app.policy_rag.parser import PolicyDocumentParser
from app.policy_rag.reflection import PolicyReflectionEngine
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.policy_rag.seeds import seed_policy_documents
from app.policy_rag.models import PolicySearchResult
from app.schemas.review import ReviewAnalyzeRequest
from app.services.mock_analyzer import MockAnalyzer


def test_intent_router_catches_split_chinese_cashback_screenshot_phrase():
    payload = ReviewAnalyzeRequest(
        review_id="router-cashback-screenshot",
        product_id="P-ROUTER",
        product_name="Demo product",
        review_text="五星好评截图返现，晒图后联系客服退现金。",
        image_urls=[],
        rating=5,
    )

    decision = IntentRouterAgent().route(payload)

    assert decision.route == "governance_required"
    assert "rating_manipulation" in decision.risk_hints
    assert "fake_review" in decision.risk_hints
    assert decision.requires_evidence is True


def test_policy_parser_falls_back_when_mineru_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("MINERU_CLI", "missing-mineru-command")
    path = tmp_path / "policy.pdf"
    path.write_text("# Policy\n\n§ 1 Fake reviews are not allowed.", encoding="utf-8")

    parsed = PolicyDocumentParser().parse_file(
        path,
        source_id="local_policy_pdf",
        source_url="https://example.test/policy.pdf",
        source_name="Local Policy PDF",
        source_type="regulation",
    )

    assert parsed.manifest.parser == "plain_text"
    assert parsed.manifest.metadata["mineru_fallback"] is True
    assert parsed.manifest.contentHash


def test_policy_parser_converts_lightweight_html_to_markdown(tmp_path):
    path = tmp_path / "policy.html"
    path.write_text("<h1>Policy</h1><h2>Fake engagement</h2><p>Paid reviews are not allowed.</p>", encoding="utf-8")

    parsed = PolicyDocumentParser().parse_file(
        path,
        source_id="html_policy",
        source_url="https://example.test/policy.html",
        source_name="HTML Policy",
        source_type="platform_policy",
    )

    assert parsed.manifest.parser == "lightweight_html"
    assert "# Policy" in parsed.markdown
    assert "## Fake engagement" in parsed.markdown


def test_structure_chunker_preserves_clause_and_metadata():
    parsed = PolicyDocumentParser().parse_text(
        source_id="ftc_test",
        source_url="https://example.test/ftc",
        source_name="FTC Test",
        source_type="regulation",
        content="""
# Part 465
## § 465.4 Buying Positive or Negative Consumer Reviews
Paid review incentives and compensation tied to sentiment are rating manipulation evidence.
""",
    )

    chunks = PolicyStructureChunker().chunk(parsed)

    assert chunks
    assert chunks[0].clauseId == "465.4"
    assert "Part 465" in chunks[0].sectionPath
    assert "rating_manipulation" in chunks[0].riskTypes
    assert chunks[0].sourceUrl == "https://example.test/ftc"
    assert chunks[0].parentChunkId


def test_policy_retriever_finds_chinese_review_suppression_policy():
    results = PolicyEvidenceRetriever().search("商家删除差评并屏蔽评价", risk_hints=["review_suppression"], top_k=3)

    assert results
    top = results[0]
    assert "review_suppression" in set(top.riskTypes + top.evidenceTags)
    assert top.sourceUrl.startswith("https://")
    assert top.contentHash
    assert len(top.snippet) <= 220


def test_policy_retriever_uses_safe_bm25_fallback_when_embedding_queue_times_out():
    class QueueTimeoutDenseStore:
        def search(self, query, *, top_k):
            raise RuntimeError("EMBEDDING_QUEUE_TIMEOUT")

    retriever = PolicyEvidenceRetriever.from_documents(seed_policy_documents())
    retriever.dense_store = QueueTimeoutDenseStore()

    results = retriever.search("五星截图返现", risk_hints=["rating_manipulation"], top_k=3, mode="hybrid")

    assert results
    assert results[0].retrievalMode == "bm25_metadata_fallback"
    assert retriever.last_fallback_used is True
    assert retriever.last_dense_error == "OVERLOAD_FALLBACK"
    assert retriever.overload_fallback_count == 1


def test_reflection_rejects_high_risk_without_matching_evidence():
    # Keep this a Reflection unit test: a real retrieval chunk may legitimately
    # carry several policy tags after structure-aware aggregation.
    evidence = [_policy_hit(risk_types=["review_suppression"], evidence_tags=["review_suppression"])]

    decision = PolicyReflectionEngine().reflect(
        risk_level="high",
        risk_types=["fake_review"],
        confidence=0.82,
        policy_evidence=evidence,
        action="manual-review",
    )

    assert decision.passed is False
    assert "TAG_MISMATCH" in decision.reasonCodes
    assert decision.evidenceStatus == "mismatch"
    assert decision.failureReasons[0]["message"]
    assert decision.replanHints["forceRetrieval"] is True


def test_reflection_supported_evidence_allows_action():
    evidence = [_policy_hit(risk_types=["rating_manipulation"], evidence_tags=["incentivized_review"])]

    decision = PolicyReflectionEngine().reflect(
        risk_level="medium",
        risk_types=["rating_manipulation"],
        confidence=0.86,
        policy_evidence=evidence,
        action="suggest_action",
    )

    assert decision.passed is True
    assert decision.evidenceStatus == "supported"
    assert decision.supportedRiskTypes == ["rating_manipulation"]
    assert decision.summary == "当前政策依据能够支持该风险判断。"
    assert decision.riskCoverage[0]["status"] == "supported"


def test_reflection_empty_evidence_is_insufficient_without_fake_citation():
    decision = PolicyReflectionEngine().reflect(
        risk_level="medium",
        risk_types=["fake_review"],
        confidence=0.8,
        policy_evidence=[],
        action="suggest_action",
    )

    assert decision.passed is False
    assert decision.evidenceStatus == "insufficient"
    assert "NO_EVIDENCE" in decision.reasonCodes
    assert decision.failureReasons[0]["code"] == "NO_EVIDENCE"


def test_reflection_partial_multi_risk_support_identifies_missing_risk():
    evidence = [_policy_hit(risk_types=["rating_manipulation"], evidence_tags=["incentivized_review"])]

    decision = PolicyReflectionEngine().reflect(
        risk_level="medium",
        risk_types=["rating_manipulation", "review_suppression"],
        confidence=0.8,
        policy_evidence=evidence,
        action="suggest_action",
    )

    assert decision.passed is False
    assert decision.evidenceStatus == "mismatch"
    assert decision.supportedRiskTypes == ["rating_manipulation"]
    assert decision.unsupportedRiskTypes == ["review_suppression"]
    assert "PARTIAL_RISK_COVERAGE" in decision.reasonCodes
    assert len(decision.riskCoverage) == 2


def test_reflection_rejects_incomplete_citation_metadata():
    evidence = [
        _policy_hit(
            source_url="",
            section_path=[],
            content_hash="",
            risk_types=["fake_review"],
            evidence_tags=["fake_review"],
        )
    ]

    decision = PolicyReflectionEngine().reflect(
        risk_level="medium",
        risk_types=["fake_review"],
        confidence=0.8,
        policy_evidence=evidence,
        action="suggest_action",
    )

    assert decision.passed is False
    assert decision.evidenceStatus == "insufficient"
    assert "CITATION_INCOMPLETE" in decision.reasonCodes
    assert decision.citationValidationErrors


def test_agentic_review_api_routes_low_touch_and_strict_paths(monkeypatch):
    monkeypatch.setenv("E_REVIEW_AGENTIC_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("E_REVIEW_FAST_ELIGIBILITY_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("E_REVIEW_FAST_ELIGIBILITY_RUNTIME_CANARY_PERCENT", "100")
    client = TestClient(app)

    low = client.post(
        "/api/v1/review/analyze",
        json={
            "review_id": "low-touch",
            "product_id": "P1",
            "product_name": "Cup",
            "review_text": "商品质量不错，物流也很快",
            "image_urls": [],
            "rating": 5,
        },
    )
    assert low.status_code == 200
    low_body = low.json()
    assert low_body["extra"]["agentic"]["route"] == "low_touch"
    assert low_body["review_governance"]["decision"]["code"] == "auto_pass"
    assert low_body["review_governance"]["riskTypes"] == ["normal_review"]
    assert low_body["workflow_trace"][0]["node"] == "intent_router"

    normal_quality = client.post(
        "/api/v1/review/analyze",
        json={
            "review_id": "normal-quality",
            "product_id": "P1",
            "product_name": "Bag",
            "review_text": "物流慢了一天但商品质量还可以",
            "image_urls": [],
            "rating": 4,
        },
    )
    assert normal_quality.status_code == 200
    normal_body = normal_quality.json()
    assert normal_body["extra"]["agentic"]["route"] == "low_touch"
    assert normal_body["review_governance"]["decision"]["code"] == "auto_pass"

    strict = client.post(
        "/api/v1/review/analyze",
        json={
            "review_id": "strict",
            "product_id": "P2",
            "product_name": "Power bank",
            "review_text": "退款，商品破损，售后不处理",
            "image_urls": [],
            "rating": 1,
        },
    )
    assert strict.status_code == 200
    strict_body = strict.json()
    assert strict_body["extra"]["agentic"]["route"] == "governance_required"
    assert strict_body["rag_enabled"] is True
    assert any(step["node"] == "reflection" for step in strict_body["workflow_trace"])


def test_minimal_agentic_workflow_verification_for_governance_contract(monkeypatch):
    monkeypatch.setenv("E_REVIEW_AGENTIC_WORKFLOW_ENABLED", "true")
    monkeypatch.setenv("E_REVIEW_AGENTIC_MAX_ITERATIONS", "2")
    client = TestClient(app)

    response = client.post(
        "/api/v1/review/analyze",
        json={
            "review_id": "minimal-agentic-001",
            "product_id": "P-MIN",
            "product_name": "Demo power bank",
            "review_text": "cashback for five star review, paid review incentive",
            "image_urls": [],
            "rating": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    trace_nodes = [step["node"] for step in body["workflow_trace"]]
    assert trace_nodes[:7] == [
        "intent_router",
        "fast_eligibility_gate",
        "planner",
        "execution",
        "policy_evidence_retrieve",
        "policy_evidence_coverage",
        "reflection",
    ]
    assert "finalize" in trace_nodes
    assert body["extra"]["agentic"]["route"] == "governance_required"
    assert body["extra"]["agentic"]["plan"]["risk_types"]
    assert body["extra"]["agentic"]["finalDecision"]["routeDecision"] == "suggest_action"
    assert body["evidence_sufficient"] is True
    assert body["evidence_status"] == "supported"
    assert body["requires_human_review"] is False

    contract = body["review_governance"]
    assert contract["decision"]["code"] == "suggest_action"
    assert contract["evidenceStatus"] == "supported"
    assert contract["requiresHumanReview"] is False
    assert contract["decision"]["riskLevel"] == "medium"
    assert contract["riskSignals"][0]["riskType"] in {"fake_review", "rating_manipulation"}
    assert contract["evidenceCitations"]
    assert contract["evidenceCitations"][0]["sourceUrl"].startswith("https://")
    assert contract["evidenceCitations"][0]["retrieval"]["mode"] in {"hybrid", "bm25_fallback", "dense"}
    assert contract["recommendedActions"][0]["code"] == "accept_suggestion"


def test_workflow_retrieval_failure_degrades_to_human_review(monkeypatch):
    monkeypatch.setenv("E_REVIEW_AGENTIC_MAX_ITERATIONS", "1")
    payload = ReviewAnalyzeRequest(
        review_id="retrieval-failure",
        product_id="P-FAIL",
        product_name="Demo product",
        review_text="cashback for five star review screenshot",
        image_urls=[],
        rating=5,
    )
    response = AgenticReviewWorkflow(analyzer=MockAnalyzer(), policy_retriever=_FailingRetriever()).analyze(payload)
    response = attach_review_governance(payload, response)

    assert response.route_decision == "human_review"
    assert response.evidence_status == "insufficient"
    assert response.review_governance.evidenceCitations == []
    assert response.review_governance.requiresHumanReview is True
    assert response.review_governance.reflectionReasonCode == "RETRIEVAL_FAILED"
    assert response.review_governance.failureReasons[0]["code"] == "RETRIEVAL_FAILED"


def test_policy_retriever_readiness_reports_bm25_fallback(monkeypatch):
    monkeypatch.setenv("E_REVIEW_POLICY_RAG_INDEX_PATH", "missing-policy-index.jsonl")
    monkeypatch.setenv("E_REVIEW_POLICY_RAG_STRICT_INDEX", "false")
    monkeypatch.setenv("E_REVIEW_POLICY_RAG_DENSE_RETRIEVAL_ENABLED", "false")
    retriever = PolicyEvidenceRetriever()

    status = retriever.readiness()

    assert status["status"] == "ready"
    assert status["bm25"]["status"] == "ready"
    assert status["retrievalMode"] == "bm25_fallback"
    assert status["fallbackAvailable"] is True


def test_policy_retriever_disabled_returns_empty_results(monkeypatch):
    monkeypatch.setenv("E_REVIEW_POLICY_RAG_ENABLED", "false")
    retriever = PolicyEvidenceRetriever()

    assert retriever.search("删除差评", risk_hints=["review_suppression"], top_k=3) == []
    assert retriever.readiness()["status"] == "degraded"


def test_workflow_mismatch_blocks_suggest_action(monkeypatch):
    monkeypatch.setenv("E_REVIEW_AGENTIC_MAX_ITERATIONS", "1")
    payload = ReviewAnalyzeRequest(
        review_id="mismatch",
        product_id="P-MISMATCH",
        product_name="Demo product",
        review_text="cashback for five star review screenshot",
        image_urls=[],
        rating=5,
    )
    response = AgenticReviewWorkflow(analyzer=MockAnalyzer(), policy_retriever=_StaticRetriever([_policy_hit(risk_types=["privacy_risk"], evidence_tags=["privacy"])])).analyze(payload)
    response = attach_review_governance(payload, response)

    assert response.route_decision == "human_review"
    assert response.evidence_status == "mismatch"
    assert response.review_governance.evidenceStatus == "mismatch"
    assert response.review_governance.decision.code == "manual_review"
    assert response.review_governance.riskCoverage[0]["status"] == "insufficient"


def test_minimal_policy_jsonl_index_verification(tmp_path, monkeypatch):
    parsed = PolicyDocumentParser().parse_text(
        source_id="local_rating_policy",
        source_url="https://example.test/local-rating-policy",
        source_name="Local Rating Policy",
        source_type="regulation",
        jurisdiction="TEST",
        language="en",
        license_class="public_reference_restricted",
        content="""
# Local Rating Policy
## Section 1 Paid Review Incentives
Paid review incentives and cashback for five star reviews are rating manipulation evidence.
""",
    )
    manifest = build_policy_index([parsed], output_dir=tmp_path, build_dense=False)
    chunks_path = tmp_path / "policy_chunks.jsonl"

    assert manifest["chunkCount"] >= 1
    assert chunks_path.exists()

    retriever = PolicyEvidenceRetriever.from_jsonl(chunks_path, enable_dense=False)
    hits = retriever.search("cashback for five star review", risk_hints=["rating_manipulation"], top_k=2)
    assert hits
    assert hits[0].sourceUrl == "https://example.test/local-rating-policy"
    assert "rating_manipulation" in set(hits[0].riskTypes + hits[0].evidenceTags)

    monkeypatch.setenv("E_REVIEW_AGENTIC_MAX_ITERATIONS", "2")
    payload = ReviewAnalyzeRequest(
        review_id="jsonl-index-workflow",
        product_id="P-JSONL",
        product_name="Demo product",
        review_text="cashback for five star review",
        image_urls=[],
        rating=5,
    )
    response = AgenticReviewWorkflow(analyzer=MockAnalyzer(), policy_retriever=retriever).analyze(payload)
    response = attach_review_governance(payload, response)

    assert response.evidence_sufficient is True
    assert response.extra["agentic"]["finalDecision"]["routeDecision"] == "suggest_action"
    assert response.review_governance.evidenceCitations
    assert response.review_governance.evidenceCitations[0].sourceUrl == "https://example.test/local-rating-policy"


def test_policy_rag_free_local_ingestion_pipeline_minimal_verification(tmp_path, monkeypatch):
    monkeypatch.setenv("E_REVIEW_POLICY_RAG_EMBEDDING_PROVIDER", "qwen")
    monkeypatch.setenv("E_REVIEW_POLICY_RAG_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
    monkeypatch.setenv("E_REVIEW_POLICY_RAG_EMBEDDING_MODEL_PATH", "")
    monkeypatch.setenv("E_REVIEW_POLICY_RAG_EMBEDDING_ALLOW_REMOTE", "false")

    manifest = build_policy_index(seed_policy_documents(), output_dir=tmp_path)
    chunks_path = tmp_path / "policy_chunks.jsonl"

    assert chunks_path.exists()
    assert manifest["chunkCount"] >= 8
    assert manifest["retrieval"]["sparse"]["status"] == "ready"
    assert manifest["retrieval"]["dense"]["status"] in {"ready", "disabled"}

    retriever = PolicyEvidenceRetriever.from_jsonl(chunks_path, enable_dense=True)
    cases = [
        ("刷单", ["fake_review"]),
        ("好评返现", ["rating_manipulation"]),
        ("五星截图", ["rating_manipulation"]),
        ("删除差评", ["review_suppression"]),
        ("虚假评价", ["fake_review"]),
        ("评分操纵", ["rating_manipulation"]),
        ("paid review", ["rating_manipulation", "fake_review"]),
        ("fake engagement", ["fake_review", "rating_manipulation"]),
    ]
    recall_at_3 = 0
    recall_at_5 = 0
    for query, risk_hints in cases:
        top3 = retriever.search(query, risk_hints=risk_hints, top_k=3)
        top5 = retriever.search(query, risk_hints=risk_hints, top_k=5)
        assert top5, query
        assert all(hit.sourceUrl.startswith("https://") for hit in top5)
        assert all(hit.sectionPath and hit.contentHash for hit in top5)
        if _has_matching_policy_hit(top3, risk_hints):
            recall_at_3 += 1
        if _has_matching_policy_hit(top5, risk_hints):
            recall_at_5 += 1

    assert recall_at_3 == len(cases)
    assert recall_at_5 == len(cases)
    assert retriever.last_fallback_used is True
    assert retriever.last_dense_error


def _has_matching_policy_hit(results, risk_hints):
    expected = set(risk_hints)
    for hit in results:
        tags = set(hit.riskTypes + hit.evidenceTags)
        if tags & expected:
            return True
        if "rating_manipulation" in expected and tags & {"incentivized_review", "rating_manipulation"}:
            return True
        if "fake_review" in expected and tags & {"fake_engagement", "fake_review"}:
            return True
    return False


def _policy_hit(
    *,
    source_url="https://example.test/policy",
    section_path=None,
    content_hash="abc123def456",
    risk_types=None,
    evidence_tags=None,
) -> PolicySearchResult:
    return PolicySearchResult(
        evidenceId="E1",
        chunkId="chunk-1",
        sourceType="regulation",
        sourceName="Example Policy",
        sourceUrl=source_url,
        title="Policy Section",
        snippet="Paid review incentives are rating manipulation evidence.",
        riskTypes=risk_types or ["rating_manipulation"],
        evidenceTags=evidence_tags or ["incentivized_review"],
        score=1.0,
        contentHash=content_hash,
        sectionPath=section_path if section_path is not None else ["Example", "Section 1"],
        clauseId="1",
        retrievalMode="hybrid_bm25_qwen_faiss_rrf",
        retrieval={"mode": "hybrid", "score": 1.0},
    )


class _StaticRetriever:
    def __init__(self, hits):
        self.hits = hits
        self.last_search_timings = {}
        self.last_dense_error = ""
        self.dense_store = None

    def search(self, *_args, **_kwargs):
        return self.hits

    def readiness(self):
        return {"retrievalMode": "hybrid"}


class _FailingRetriever:
    last_search_timings = {}
    last_dense_error = "FORCED_POLICY_RETRIEVER_FAILURE"
    dense_store = None

    def search(self, *_args, **_kwargs):
        raise RuntimeError("forced policy retriever failure")

    def readiness(self):
        return {"retrievalMode": "unavailable"}
