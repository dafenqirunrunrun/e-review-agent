from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.agentic_workflow.workflow import AgenticReviewWorkflow
from app.core.config import PolicyRagSettings
from app.policy_rag.models import PolicyChunk, PolicySearchResult
from app.policy_rag.reranker import PolicyEvidenceReranker, PolicyRerankOutcome
from app.schemas.review import ReviewAnalyzeRequest
from app.services.mock_analyzer import MockAnalyzer


class _ReverseModel:
    def rerank(self, _query, rows):
        output = []
        for score, row in zip(range(len(rows), 0, -1), reversed(rows), strict=True):
            output.append({**row, "rerank_score": float(score)})
        output.sort(key=lambda item: item["rerank_score"], reverse=True)
        return output, 1.25


class _FailingModel:
    def rerank(self, _query, _rows):
        raise RuntimeError("forced model failure")


class _StaticRetriever:
    def __init__(self, hits: list[PolicySearchResult], chunks: dict[str, PolicyChunk]):
        self.hits = hits
        self.chunks = chunks
        self.requested_top_k: list[int] = []
        self.last_search_timings = {
            "bm25Ms": 7.0,
            "faissSearchMs": 3.0,
            "rrfMs": 1.0,
        }
        self.last_dense_error = ""
        self.dense_store = SimpleNamespace(
            provider=SimpleNamespace(
                metadata=lambda: {
                    "queueWaitMs": 2.0,
                    "embeddingComputeMs": 11.0,
                }
            )
        )

    def search(self, *_args, **kwargs):
        self.requested_top_k.append(int(kwargs["top_k"]))
        return self.hits[: kwargs["top_k"]]

    def chunk_for_id(self, chunk_id: str):
        return self.chunks.get(chunk_id)

    def readiness(self):
        return {"retrievalMode": "hybrid"}

    def observability_metadata(self):
        return {"policyIndexVersion": "test-index"}


class _SpyReranker:
    enabled = True
    candidate_k = 5

    def __init__(self):
        self.calls = 0

    def rerank(self, _query, candidates, *, chunk_resolver):
        del chunk_resolver
        self.calls += 1
        ranked_candidates = [
            item.model_copy(update={"evidenceId": f"E{rank}"})
            for rank, item in enumerate(reversed(candidates[:5]), start=1)
        ]
        evidence = ranked_candidates[:3]
        return PolicyRerankOutcome(
            evidence=evidence,
            ranked_candidates=ranked_candidates,
            metadata={
                "effectiveMode": "hybrid_bge_reranked",
                "candidateCount": len(candidates),
                "outputCount": len(evidence),
                "fallbackUsed": False,
                "fallbackReason": "",
                "durationMs": 1.0,
            },
        )

    def observability_metadata(self):
        return {"policyRerankerEnabled": True, "policyRerankerStatus": "ready"}


def test_policy_reranker_reorders_top5_to_top3(tmp_path):
    config = _config(tmp_path)
    chunks, hits = _fixtures()
    reranker = PolicyEvidenceReranker(config, model_factory=lambda *_args: _ReverseModel())

    result = reranker.rerank("五星截图返现", hits, chunk_resolver=chunks.get)

    assert [item.chunkId for item in result.evidence] == ["policy-chunk-05", "policy-chunk-04", "policy-chunk-03"]
    assert [item.evidenceId for item in result.evidence] == ["E1", "E2", "E3"]
    assert [item.chunkId for item in result.ranked_candidates] == [
        "policy-chunk-05",
        "policy-chunk-04",
        "policy-chunk-03",
        "policy-chunk-02",
        "policy-chunk-01",
    ]
    assert result.metadata["effectiveMode"] == "hybrid_bge_reranked"
    assert result.metadata["fallbackUsed"] is False


def test_policy_reranker_allows_a_bounded_per_request_candidate_budget(tmp_path):
    config = _config(tmp_path)
    chunks, hits = _fixtures(count=8)
    reranker = PolicyEvidenceReranker(config, model_factory=lambda *_args: _ReverseModel())

    result = reranker.rerank("五星截图返现", hits, chunk_resolver=chunks.get, candidate_limit=7)

    assert len(result.ranked_candidates) == 7
    assert result.metadata["candidateK"] == 7
    assert result.metadata["effectiveMode"] == "hybrid_bge_reranked"


def test_policy_reranker_failure_preserves_rrf_order(tmp_path):
    config = _config(tmp_path)
    chunks, hits = _fixtures()
    reranker = PolicyEvidenceReranker(config, model_factory=lambda *_args: _FailingModel())

    result = reranker.rerank("五星截图返现", hits, chunk_resolver=chunks.get)

    assert [item.chunkId for item in result.evidence] == ["policy-chunk-01", "policy-chunk-02", "policy-chunk-03"]
    assert [item.chunkId for item in result.ranked_candidates] == [
        "policy-chunk-01",
        "policy-chunk-02",
        "policy-chunk-03",
        "policy-chunk-04",
        "policy-chunk-05",
    ]
    assert result.metadata["effectiveMode"] == "rrf_fallback"
    assert result.metadata["fallbackUsed"] is True
    assert result.metadata["fallbackReason"] == "RERANKER_EXECUTION_FAILED"


def test_policy_reranker_warmup_is_explicit_and_fail_open(tmp_path):
    disabled_config = _config(tmp_path / "disabled")
    disabled_config.reranker_warmup_enabled = False
    disabled = PolicyEvidenceReranker(disabled_config, model_factory=lambda *_args: _ReverseModel())
    assert disabled.warmup()["status"] == "skipped"

    enabled_config = _config(tmp_path / "enabled")
    enabled_config.reranker_warmup_enabled = True
    ready = PolicyEvidenceReranker(enabled_config, model_factory=lambda *_args: _ReverseModel()).warmup()
    degraded = PolicyEvidenceReranker(enabled_config, model_factory=lambda *_args: _FailingModel()).warmup()

    assert ready["status"] == "ready"
    assert ready["modelComputeMs"] == 1.25
    assert degraded["status"] == "degraded"
    assert degraded["reason"] == "RERANKER_EXECUTION_FAILED"


def test_workflow_runs_b2_only_for_governance_path(monkeypatch):
    monkeypatch.setenv("E_REVIEW_AGENTIC_MAX_ITERATIONS", "1")
    monkeypatch.setenv("E_REVIEW_AGENTIC_CHECKPOINT_ENABLED", "false")
    chunks, hits = _fixtures()
    retriever = _StaticRetriever(hits, chunks)
    reranker = _SpyReranker()
    workflow = AgenticReviewWorkflow(
        analyzer=MockAnalyzer(),
        policy_retriever=retriever,
        policy_reranker=reranker,
    )

    strict = workflow.analyze(
        ReviewAnalyzeRequest(
            review_id="b2-strict",
            product_id="P-B2",
            product_name="Demo product",
            review_text="五星好评截图返现，晒图联系客服退现金。",
            image_urls=[],
            rating=5,
        )
    )
    normal = workflow.analyze(
        ReviewAnalyzeRequest(
            review_id="b2-normal",
            product_id="P-B2",
            product_name="Demo product",
            review_text="包装完整，物流正常，使用体验不错。",
            image_urls=[],
            rating=5,
        )
    )

    assert retriever.requested_top_k == [20]
    assert reranker.calls == 1
    assert strict.extra["agentic"]["reranker"]["effectiveMode"] == "hybrid_bge_reranked"
    assert [item.node for item in strict.workflow_trace].count("policy_evidence_rerank") == 1
    assert strict.evidence_status == "supported"
    assert strict.extra["agentic"]["evidenceBundle"]["iterations"][0]["citationCount"] == 5
    assert len(strict.extra["agentic"]["evidenceBundle"]["citations"]) == 3
    assert [item.node for item in strict.workflow_trace].count("policy_evidence_coverage") == 1
    assert normal.extra["agentic"]["route"] == "low_touch"
    assert all(item.node != "policy_evidence_rerank" for item in normal.workflow_trace)
    assert normal.extra["latencyBreakdown"]["embeddingComputeMs"] == 0.0
    assert normal.extra["latencyBreakdown"]["bm25Ms"] == 0.0
    assert normal.extra["latencyBreakdown"]["policyRerankerMs"] == 0.0
    assert normal.extra["policyRetrieval"]["actualMode"] == "not_executed"


def _config(model_path: Path) -> PolicyRagSettings:
    model_path.mkdir(parents=True, exist_ok=True)
    (model_path / "config.json").write_text("{}", encoding="utf-8")
    return PolicyRagSettings(
        reranker_enabled=True,
        reranker_model_path=str(model_path),
        reranker_candidate_k=5,
        reranker_final_k=3,
        reranker_latency_budget_ms=2500,
    )


def _fixtures(count: int = 5) -> tuple[dict[str, PolicyChunk], list[PolicySearchResult]]:
    chunks: dict[str, PolicyChunk] = {}
    hits: list[PolicySearchResult] = []
    for index in range(1, count + 1):
        chunk_id = f"policy-chunk-{index:02d}"
        chunk = PolicyChunk(
            chunkId=chunk_id,
            documentId="policy-doc",
            sourceName="Example Policy",
            sourceUrl=f"https://example.test/policy#{index}",
            sourceType="regulation",
            heading=f"Policy clause {index}",
            sectionPath=["Part 1", f"Clause {index}"],
            clauseId=str(index),
            text="Paid reviews, cashback and five-star screenshot incentives manipulate ratings.",
            parentChunkId="policy-parent-01",
            riskTypes=["fake_review", "rating_manipulation"],
            evidenceTags=["paid_review", "rating_manipulation"],
            contentHash=f"content-hash-{index:02d}",
            tokenCount=12,
        )
        chunks[chunk_id] = chunk
        hits.append(
            PolicySearchResult(
                evidenceId=f"E{index}",
                chunkId=chunk_id,
                sourceType=chunk.sourceType,
                sourceName=chunk.sourceName,
                sourceUrl=chunk.sourceUrl,
                title=chunk.heading,
                snippet=chunk.text,
                riskTypes=chunk.riskTypes,
                evidenceTags=chunk.evidenceTags,
                score=1.0 / index,
                contentHash=chunk.contentHash,
                sectionPath=chunk.sectionPath,
                clauseId=chunk.clauseId,
                retrievalMode="hybrid_bm25_qwen_faiss_rrf",
                retrieval={"mode": "hybrid", "score": 1.0 / index},
            )
        )
    return chunks, hits
