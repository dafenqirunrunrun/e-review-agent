import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.agent_rag.contracts import AgentRagRequest
from app.agent_rag.phase2_retrieval import RetrievalCandidate
from app.agent_rag.reranker import (
    GovernedReranker,
    LocalModelReranker,
    RerankerConfig,
    RerankerUnavailable,
    audit_reranker_model_asset,
)
from app.agent_rag.runtime import AgentRagRuntime


ROOT = Path(__file__).resolve().parents[2]


def _candidate(chunk_id: str, score: float = 0.1, *, tenant_id: str = "tenant-a", active: bool = True) -> RetrievalCandidate:
    return RetrievalCandidate(
        retrieverType="fixture",
        tenantId=tenant_id,
        documentId=f"doc-{chunk_id}",
        chunkId=chunk_id,
        sparseScore=score,
        sparseRank=1,
        rawRank=1,
        fusionScore=score,
        fusionRank=1,
        row={
            "tenant_id": tenant_id,
            "document_id": f"doc-{chunk_id}",
            "chunk_id": chunk_id,
            "content": "refund broken after-sales policy" if chunk_id.endswith("a") else "general shipping policy",
            "content_hash": f"{chunk_id}abc123abc123",
            "source_type": "policy",
            "title": f"Title {chunk_id}",
            "active": active,
            "deleted": False,
        },
    )


def test_v200_phase3b_deterministic_reranker_is_stable_and_bounded():
    config = RerankerConfig(requested_type="deterministic", final_k=2)
    candidates = [_candidate("c", 0.5), _candidate("a", 0.5), _candidate("b", 0.4)]
    result = GovernedReranker(config).rerank("general policy", candidates, top_k=2, tenant_id="tenant-a")
    assert [item.chunkId for item in result.candidates] == ["c", "a"]
    assert result.effectiveType == "deterministic"
    assert result.inputCount == 3
    assert result.outputCount == 2
    assert result.fallbackUsed is False


def test_v200_phase3b_tenant_scope_violation_is_rejected_before_any_rerank():
    config = RerankerConfig(requested_type="local-model", model_path="", real_required=False)
    with pytest.raises(RerankerUnavailable, match="TENANT_SCOPE_VIOLATION"):
        GovernedReranker(config).rerank("refund", [_candidate("a"), _candidate("b", 0.2, tenant_id="tenant-b")], top_k=2, tenant_id="tenant-a")


def test_v200_phase3b_inactive_candidate_is_rejected():
    config = RerankerConfig(requested_type="deterministic")
    with pytest.raises(RerankerUnavailable, match="INACTIVE_CANDIDATE"):
        GovernedReranker(config).rerank("refund", [_candidate("a", active=False)], top_k=1, tenant_id="tenant-a")


def test_v200_phase3b_model_missing_is_explicit_and_sanitized(tmp_path):
    config = RerankerConfig(requested_type="local-model", model_path=str(tmp_path / "missing"), model_name="local-reranker")
    audit = audit_reranker_model_asset(config)
    assert audit.configured is True
    assert audit.exists is False
    assert audit.pathHint == "missing"
    assert str(tmp_path) not in json.dumps(audit.__dict__)
    result = GovernedReranker(config).rerank("refund", [_candidate("a", 0.1)], top_k=1, tenant_id="tenant-a")
    assert result.fallbackUsed is True
    assert result.fallbackReason == "MODEL_NOT_FOUND"


def test_v200_phase3b_real_required_does_not_pretend_fallback(tmp_path):
    config = RerankerConfig(requested_type="local-model", model_path=str(tmp_path / "missing"), real_required=True)
    with pytest.raises(RerankerUnavailable, match="MODEL_NOT_FOUND"):
        GovernedReranker(config).rerank("refund", [_candidate("a", 0.1)], top_k=1, tenant_id="tenant-a")


def test_v200_phase3b_model_invalid_score_falls_back():
    class BadScoreReranker:
        def rerank(self, query, candidates, *, top_k, tenant_id="", request_id=""):
            del query, candidates, top_k, tenant_id, request_id
            raise RerankerUnavailable("INVALID_SCORE")

    config = RerankerConfig(requested_type="local-model", model_path="configured")
    result = GovernedReranker(config, model_reranker=BadScoreReranker()).rerank("refund", [_candidate("a", 0.1)], top_k=1, tenant_id="tenant-a")
    assert result.fallbackUsed is True
    assert result.fallbackReason == "INVALID_SCORE"


def test_v200_phase3b_evidence_bundle_records_reranker_fields(monkeypatch):
    monkeypatch.setenv("RAG_RERANKER_TYPE", "local-model")
    monkeypatch.setenv("RAG_RERANKER_MODEL_PATH", "")
    monkeypatch.delenv("AGENT_RAG_V22_ASSET_MANIFEST", raising=False)
    runtime = AgentRagRuntime(
        chunks=[
            {
                "tenant_id": "tenant-a",
                "document_id": "doc-1",
                "chunk_id": "chunk-1",
                "content": "refund broken after-sales policy",
                "content_hash": "abc123abc123",
                "source_type": "policy",
                "title": "Refund policy",
            }
        ]
    )
    result, bundle = runtime.analyze(
        AgentRagRequest(
            requestId="req-reranker-evidence",
            tenantId="tenant-a",
            subjectId="review-reranker",
            query="refund broken item",
        )
    )
    assert result.retrieval.requestedRerankerType == "local-model"
    assert result.retrieval.rerankerFallbackUsed is True
    assert result.retrieval.rerankerFallbackReason == "MODEL_PATH_NOT_CONFIGURED"
    assert bundle.requestedRerankerType == "local-model"
    assert bundle.rerankerFallbackUsed is True


def test_v200_phase3b_gate_reports_blocked_without_model_env(monkeypatch):
    monkeypatch.setenv("RAG_RERANKER_TYPE", "local-model")
    monkeypatch.delenv("RAG_RERANKER_MODEL_PATH", raising=False)
    completed = subprocess.run(
        [sys.executable, "ai-service/scripts/readiness/run_agent_rag_phase3b_gate.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "AGENT_RAG_RERANKER_CONTRACT_PASS" in completed.stdout
    assert "AGENT_RAG_MODEL_RERANKER_BLOCKED" in completed.stdout
    gate = json.loads((ROOT / "artifacts" / "agent-rag" / "v2.0-phase3b" / "phase3b-gate-result.json").read_text(encoding="utf-8"))
    assert gate["modelRerankerStatus"] == "BLOCKED"


@pytest.mark.real_reranker
@pytest.mark.requires_model_asset
def test_v200_phase3b_real_local_reranker_smoke():
    model_path = os.getenv("RAG_RERANKER_MODEL_PATH", "")
    if not model_path:
        pytest.skip("RERANKER_MODEL_ASSET_UNAVAILABLE_SKIP")
    config = RerankerConfig(requested_type="local-model", model_path=model_path, model_name=os.getenv("RAG_RERANKER_MODEL_NAME", ""), device=os.getenv("RAG_RERANKER_DEVICE", "cpu"))
    result = LocalModelReranker(config).rerank("refund broken after-sales", [_candidate("a", 0.1), _candidate("b", 0.2)], top_k=1, tenant_id="tenant-a")
    assert result.effectiveType == "local-model"
    assert result.fallbackUsed is False
    assert result.modelFingerprint


@pytest.mark.real_reranker_runtime
@pytest.mark.requires_model_asset
def test_v22_real_reranker_executes_through_formal_agent_runtime(monkeypatch):
    manifest = os.getenv("AGENT_RAG_V22_ASSET_MANIFEST", "")
    if not manifest:
        pytest.skip("V22_ASSET_MANIFEST_UNAVAILABLE_SKIP")
    monkeypatch.setenv("RAG_RERANKER_TYPE", "local-model")
    monkeypatch.setenv("RAG_RERANKER_PROVIDER_IMPL", "flagembedding")
    monkeypatch.setenv("RAG_RERANKER_USE_FP16", "true")
    monkeypatch.setenv("RAG_RERANKER_NORMALIZE", "true")
    monkeypatch.setenv("RAG_RERANKER_CANDIDATE_K", "12")
    monkeypatch.setenv("RAG_RERANKER_FINAL_K", "2")
    monkeypatch.setenv("RAG_RERANKER_BATCH_SIZE", "4")
    monkeypatch.setenv("RAG_RERANKER_MAX_LENGTH", "384")
    monkeypatch.setenv("RAG_RERANKER_QUEUE_TIMEOUT_MS", "15000")
    monkeypatch.setenv("RAG_RERANKER_TIMEOUT_MS", "45000")
    monkeypatch.setenv("RAG_REAL_RERANKER_REQUIRED", "true")
    chunks = [
        {
            "tenant_id": "tenant-a",
            "document_id": "refund-fraud-policy",
            "chunk_id": "refund-fraud-1",
            "content": "Refund fraud review: repeated no-receipt refund request conflicts with signed logistics evidence.",
            "content_hash": "refund_fraud_hash_001",
            "source_type": "policy",
            "title": "Refund fraud policy",
            "active": True,
            "deleted": False,
            "trust_level": "internal_verified",
        },
        {
            "tenant_id": "tenant-a",
            "document_id": "general-policy",
            "chunk_id": "general-1",
            "content": "General packaging color and weather comments are ordinary low risk review context.",
            "content_hash": "general_policy_hash_1",
            "source_type": "policy",
            "title": "General policy",
            "active": True,
            "deleted": False,
            "trust_level": "internal_verified",
        },
    ]
    runtime = AgentRagRuntime(chunks=chunks)
    result, bundle = runtime.analyze(
        AgentRagRequest(
            requestId="v22-real-reranker-runtime",
            tenantId="tenant-a",
            subjectId="review-v22-reranker",
            query="refund fraud signed logistics no receipt",
            retrieval={"enabled": True, "topK": 4, "rerankTopK": 2},
        )
    )
    assert result.retrieval.requestedRerankerType == "local-model"
    assert result.retrieval.effectiveRerankerType == "local-model"
    assert result.retrieval.rerankerFallbackUsed is False
    assert result.retrieval.rerankerInputCount > 0
    assert result.retrieval.rerankerOutputCount > 0
    assert result.retrieval.rerankerModelId == "BAAI/bge-reranker-v2-m3"
    assert result.retrieval.rerankerRevision == "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
    assert result.retrieval.rerankerFingerprint
    assert bundle.effectiveRerankerType == "local-model"
    assert bundle.rerankerFallbackUsed is False
