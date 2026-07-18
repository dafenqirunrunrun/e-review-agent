import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.llm.service import LlmReviewService
from app.main import app
from app.rag_v2.corpus_loader import load_cases, load_jsonl
from app.rag_v2.dense_encoder import BgeM3Encoder
from app.rag_v2.faiss_store import FaissVectorStore
from app.rag_v2.hybrid_retriever import HybridRetriever
from app.rag_v2.reranker import NeuralReranker, RuleReranker
from app.rag_v2.tfidf_retriever import TfidfRetriever
from app.schemas.review import ReviewAnalyzeRequest
from app.services.mock_analyzer import MockAnalyzer
from app.services.rule_agent import RuleAgentWorkflow


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "data/rag/cases/risk_cases_240.jsonl"
QUERIES = ROOT / "data/rag/golden_queries/golden_queries_80.jsonl"


def test_rag_dataset_loads_expected_counts_and_unique_ids():
    cases = load_cases(CASES)
    queries = load_jsonl(QUERIES)
    assert len(cases) == 240
    assert len(queries) == 80
    assert len({row["case_id"] for row in cases}) == 240
    assert all(row["hard_negative_case_ids"] for row in queries)


def test_tfidf_retriever_finds_damage_case():
    retriever = TfidfRetriever(load_cases(CASES))
    hits = retriever.search("商品外壳破损，需要售后核验", 5)
    assert hits
    assert hits[0]["case_id"].startswith("CASE-DAMAGED")
    assert hits[0]["lexical_score"] > 0


def test_tfidf_empty_query_is_safe():
    retriever = TfidfRetriever(load_cases(CASES))
    assert retriever.search("", 5) == []
    assert retriever.search("   ", 5) == []


def test_bge_encoder_reports_missing_model(tmp_path):
    encoder = BgeM3Encoder(tmp_path / "missing")
    assert not encoder.available
    with pytest.raises(RuntimeError, match="BGE_M3_NOT_AVAILABLE"):
        encoder.encode_queries(["query"])


@pytest.mark.skipif(importlib.util.find_spec("faiss") is None, reason="faiss not installed in base test environment")
def test_faiss_build_load_and_search(tmp_path):
    cases = load_cases(CASES)[:3]
    vectors = np.eye(3, dtype="float32")
    store = FaissVectorStore(tmp_path / "index.faiss", tmp_path / "meta.json")
    meta = store.build(vectors, cases, "test-model", 3)
    assert meta["case_count"] == 3
    loaded = FaissVectorStore(tmp_path / "index.faiss", tmp_path / "meta.json")
    assert loaded.load()["dimension"] == 3
    assert loaded.search(np.array([1, 0, 0], dtype="float32"), 1)[0]["case_id"] == cases[0]["case_id"]


class FakeEncoder:
    available = True

    def encode_queries(self, texts):
        return np.array([[1.0, 0.0]], dtype="float32")


class FakeStore:
    def __init__(self, cases):
        self.cases = cases

    def search(self, vector, top_k):
        return [dict(self.cases[1], dense_score=0.95), dict(self.cases[0], dense_score=0.30)]


def test_hybrid_score_fusion_returns_component_scores():
    cases = load_cases(CASES)[:4]
    retriever = HybridRetriever(
        cases, TfidfRetriever(cases), FakeEncoder(), FakeStore(cases), RuleReranker(), None,
        {"alpha": 0.3, "beta": 0.4, "gamma": 0.2, "delta": 0.1}, 4,
    )
    result = retriever.search({"query_text": "破损", "top_k": 2, "strategy": "hybrid"})
    assert result["hits"]
    assert {"final_score", "lexical_score", "dense_score", "metadata_match_score"} <= set(result["hits"][0])


def test_neural_reranker_unavailable_falls_back_to_rule(tmp_path):
    cases = load_cases(CASES)[:4]
    retriever = HybridRetriever(
        cases, TfidfRetriever(cases), FakeEncoder(), FakeStore(cases), RuleReranker(),
        NeuralReranker(tmp_path / "missing"),
        {"alpha": 0.3, "beta": 0.4, "gamma": 0.2, "delta": 0.1}, 4,
    )
    result = retriever.search({"query_text": "破损", "top_k": 2, "strategy": "hybrid_rerank"})
    assert result["reranker_provider"] == "rule"


def test_dense_strategy_without_index_returns_explicit_fallback(tmp_path):
    cases = load_cases(CASES)[:4]
    retriever = HybridRetriever(
        cases, TfidfRetriever(cases), BgeM3Encoder(tmp_path / "missing"),
        FaissVectorStore(tmp_path / "none.faiss", tmp_path / "none.json"), RuleReranker(), None,
        {"alpha": 0.3, "beta": 0.4, "gamma": 0.2, "delta": 0.1}, 4,
    )
    result = retriever.search({"query_text": "破损", "top_k": 2, "strategy": "dense"})
    assert result["hits"] == []
    assert result["fallback_used"] is True


class FakeRagService:
    def search(self, request):
        return {
            "strategy": "hybrid_rerank", "candidate_count": 2, "hit_count": 1, "top_score": 0.91,
            "latency_ms": 12, "embedding_provider": "bge_m3", "reranker_provider": "rule",
            "fallback_used": False,
            "hits": [{"case_id": "CASE-DAMAGED-01", "title": "破损案例", "risk_type": "after_sales_risk",
                      "risk_level": "high", "evidence": ["破损"], "operation_suggestion": "人工核验", "final_score": 0.91}],
        }


def test_agent_rag_integration_and_observability(monkeypatch):
    monkeypatch.setenv("E_REVIEW_RAG_V2_ENABLED", "true")
    monkeypatch.setenv("E_REVIEW_RAG_V2_STRATEGY", "hybrid_rerank")
    monkeypatch.setenv("E_REVIEW_LLM_PROVIDER", "local_rule_fallback")
    import app.rag_v2.service as rag_service_module
    monkeypatch.setattr(rag_service_module, "_SERVICE", FakeRagService())
    service = LlmReviewService(RuleAgentWorkflow(MockAnalyzer()))
    response = service.analyze(ReviewAnalyzeRequest(
        review_id="rag-test", product_id="1", product_name="test", review_text="收到时破损，要求退款", rating=1
    ))
    assert response.rag_enabled is True
    assert response.retrieved_case_ids == ["CASE-DAMAGED-01"]
    assert response.route_decision == "human_review"
    tools = [row.tool_name for row in response.workflow_trace]
    assert "HybridRagRetrieverTool" in tools
    assert "EvidenceSufficiencyTool" in tools
    assert "RerankerTool" in tools


def test_rag_status_api_is_available():
    body = TestClient(app).get("/api/v1/rag-v2/status").json()
    assert body["corpus_size"] == 240
    assert body["embedding_provider"] == "bge_m3"
    assert "index_available" in body
