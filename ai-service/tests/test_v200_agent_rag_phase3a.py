import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from app.agent_rag.embedding_provider import BgeM3EmbeddingProvider, BgeM3ProviderConfig, DisabledEmbeddingProvider, HashEmbeddingProvider
from app.agent_rag.faiss_index import FaissVectorIndex, IndexCompatibilityError
from app.agent_rag.phase3a_retrieval import GovernedHybridRuntime
from app.agent_rag.contracts import AgentRagRequest
from app.agent_rag.runtime import AgentRagRuntime, _knowledge_chunks_from_rows
from app.agent_rag.target_mode import AgentRagTargetConfig

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ai-service" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from agent_rag_phase3a_common import phase3a_chunks


def _chunks():
    return phase3a_chunks("tenant-a")[1]


def test_v200_phase3a_hash_provider_contract_and_metadata():
    provider = HashEmbeddingProvider(dimensions=16)
    matrix = provider.embed_documents(["refund broken", "unsafe smoke"])
    assert matrix.shape == (2, 16)
    assert np.allclose(np.linalg.norm(matrix, axis=1), 1.0, atol=1e-5)
    metadata = provider.metadata()
    assert metadata["providerType"] == "hash"
    assert metadata["dimension"] == 16
    assert metadata["modelFingerprint"]
    with pytest.raises(ValueError, match="EMBEDDING_EMPTY_BATCH"):
        provider.embed_documents([])
    with pytest.raises(ValueError, match="EMBEDDING_EMPTY_TEXT"):
        provider.embed_documents([""])


def test_v200_phase3a_bge_missing_asset_is_explicit_not_service_fatal(tmp_path):
    provider = BgeM3EmbeddingProvider(BgeM3ProviderConfig(model_path=tmp_path / "missing", load_on_startup=False))
    assert provider.health()["status"] == "not_loaded"
    with pytest.raises(RuntimeError, match="BGE_M3_MODEL_ASSET_UNAVAILABLE"):
        provider.embed_query("refund")
    assert provider.health()["status"] == "failed"


def test_v200_phase3a_faiss_manifest_activation_and_compatibility(tmp_path):
    chunks = _chunks()
    provider = HashEmbeddingProvider(dimensions=32)
    index = FaissVectorIndex(tmp_path / "faiss")
    manifest = index.build(chunks=chunks, provider=provider, tenant_id="tenant-a", index_version="hash-v1")
    assert manifest.vectorCount == len(chunks)
    active = index.activate("hash-v1", provider.metadata(), tenant_id="tenant-a")
    assert active.status == "active"
    hits, loaded = index.search(provider.embed_query("refund broken"), provider.metadata(), tenant_id="tenant-a", top_k=5)
    assert loaded.indexVersion == "hash-v1"
    assert hits
    bad = dict(provider.metadata())
    bad["modelFingerprint"] = "bad"
    with pytest.raises(IndexCompatibilityError, match="MODEL_FINGERPRINT_MISMATCH"):
        index.validate_candidate("hash-v1", bad, tenant_id="tenant-a")
    bad = dict(provider.metadata())
    bad["dimension"] = 999
    with pytest.raises(IndexCompatibilityError, match="EMBEDDING_DIMENSION_MISMATCH"):
        index.validate_candidate("hash-v1", bad, tenant_id="tenant-a")


def test_v200_phase3a_runtime_fallback_does_not_pretend_real_dense():
    runtime = GovernedHybridRuntime(chunks=_chunks(), provider=DisabledEmbeddingProvider("MODEL_MISSING"), fallback_provider="hash", real_dense_required=False)
    candidates, trace = runtime.search("refund broken", tenant_id="tenant-a", mode="hybrid-real", fusion_top_k=5)
    assert candidates
    assert trace.denseFallbackUsed is True
    assert trace.effectiveRetrievalMode == "hybrid-hash"
    assert trace.denseProvider == "hash"


def test_v22_agent_runtime_can_use_phase3a_dense_path(tmp_path):
    chunks = _chunks()[:10]
    provider = HashEmbeddingProvider(dimensions=32)
    index = FaissVectorIndex(tmp_path / "agent-runtime-faiss")
    manifest = index.build(chunks=chunks, provider=provider, tenant_id="tenant-a", index_version="agent-runtime-hash-v1")
    index.activate(manifest.indexVersion, provider.metadata(), tenant_id="tenant-a")
    dense_runtime = GovernedHybridRuntime(chunks=chunks, provider=provider, faiss_index=index, real_dense_required=True)
    target_config = AgentRagTargetConfig(
        target_mode="governed-local",
        dense_provider="hash",
        bge_m3_provider_impl="legacy-cls",
        default_retrieval_mode="hybrid-real",
        reranker_type="deterministic",
        llm_provider="rule",
        rule_fallback_enabled=True,
        evidence_enabled=True,
        real_dense_required=True,
    )
    runtime = AgentRagRuntime(
        chunks=[chunk.as_retriever_row() for chunk in chunks],
        dense_runtime=dense_runtime,
        target_config=target_config,
    )
    result, bundle = runtime.analyze(
        AgentRagRequest(requestId="phase3a-agent-runtime", tenantId="tenant-a", subjectId="dense-1", query="refund broken after-sales")
    )
    assert result.retrieval.requestedRetrievalMode == "hybrid-real"
    assert result.retrieval.effectiveRetrievalMode == "hybrid-real"
    assert result.retrieval.denseProvider == "hash"
    assert result.retrieval.faissIndexType == "IndexFlatIP"
    assert result.retrieval.embeddingDurationMs >= 0
    assert bundle.effectiveRetrievalMode == "hybrid-real"


def test_v22_agent_runtime_maps_legacy_taxonomy_source_type():
    chunks = _knowledge_chunks_from_rows([
        {
            "tenant_id": "__public__",
            "document_id": "public-review-taxonomy",
            "chunk_id": "public-taxonomy-1",
            "source_type": "taxonomy",
            "content": "Public taxonomy maps refund and broken package signals to governed actions.",
            "content_hash": "public_taxonomy_hash1",
            "active": True,
        }
    ])
    assert len(chunks) == 1
    assert chunks[0].sourceType == "public-regulation"


def test_v200_phase3a_gate_reports_not_verified_without_model_env(monkeypatch):
    monkeypatch.delenv("RAG_BGE_M3_MODEL_PATH", raising=False)
    completed = subprocess.run([sys.executable, "ai-service/scripts/readiness/run_agent_rag_phase3a_gate.py"], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "AGENT_RAG_REAL_DENSE_NOT_VERIFIED" in completed.stdout
    gate = json.loads((ROOT / "artifacts" / "agent-rag" / "v2.0-phase3a" / "phase3a-gate-result.json").read_text(encoding="utf-8"))
    assert gate["status"] == "NOT_VERIFIED"


@pytest.mark.real_dense
@pytest.mark.requires_model_asset
def test_v200_phase3a_real_bge_provider_numerics():
    model_path = os.getenv("RAG_BGE_M3_MODEL_PATH", "")
    if not model_path:
        pytest.skip("MODEL_ASSET_UNAVAILABLE_SKIP")
    provider = BgeM3EmbeddingProvider(BgeM3ProviderConfig(model_path=Path(model_path), device=os.getenv("RAG_BGE_M3_DEVICE", "cpu"), batch_size=2, max_length=128, normalize=True))
    try:
        vectors = provider.embed_documents(["refund broken after-sales", "unsafe smoke fire", "refund broken after-sales"])
        assert vectors.shape[0] == 3
        assert vectors.shape[1] > 0
        assert np.isfinite(vectors).all()
        assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-3)
        assert np.allclose(vectors[0], vectors[2], atol=1e-5)
        assert not np.allclose(vectors[0], vectors[1], atol=1e-5)
        assert provider.metadata()["providerType"] == "bge-m3-legacy-cls"
        assert provider.metadata()["providerImpl"] == "legacy-cls"
    finally:
        provider.close()


@pytest.mark.real_dense
@pytest.mark.requires_model_asset
def test_v200_phase3a_real_bge_provider_health_and_metadata():
    model_path = os.getenv("RAG_BGE_M3_MODEL_PATH", "")
    if not model_path:
        pytest.skip("MODEL_ASSET_UNAVAILABLE_SKIP")
    provider = BgeM3EmbeddingProvider(BgeM3ProviderConfig(model_path=Path(model_path), device=os.getenv("RAG_BGE_M3_DEVICE", "cpu"), batch_size=1, max_length=64, normalize=True))
    try:
        provider.embed_query("provider health metadata smoke")
        health = provider.health()
        metadata = provider.metadata()
        assert health["status"] == "ready"
        assert metadata["providerType"] == "bge-m3-legacy-cls"
        assert metadata["providerImpl"] == "legacy-cls"
        assert metadata["dimension"] == 1024
        assert metadata["modelFingerprint"]
    finally:
        provider.close()


@pytest.mark.real_dense
@pytest.mark.requires_model_asset
def test_v200_phase3a_real_faiss_build_search_and_compatibility(tmp_path):
    model_path = os.getenv("RAG_BGE_M3_MODEL_PATH", "")
    if not model_path:
        pytest.skip("MODEL_ASSET_UNAVAILABLE_SKIP")
    provider = BgeM3EmbeddingProvider(BgeM3ProviderConfig(model_path=Path(model_path), device=os.getenv("RAG_BGE_M3_DEVICE", "cpu"), batch_size=4, max_length=128, normalize=True))
    index = FaissVectorIndex(tmp_path / "real-faiss")
    try:
        chunks = _chunks()[:20]
        manifest = index.build(chunks=chunks, provider=provider, tenant_id="tenant-a", index_version="real-v1")
        index.activate(manifest.indexVersion, provider.metadata(), tenant_id="tenant-a")
        hits, loaded = index.search(provider.embed_query("refund broken after-sales"), provider.metadata(), tenant_id="tenant-a", top_k=3)
        assert hits
        assert loaded.modelFingerprint == provider.metadata()["modelFingerprint"]
        bad = dict(provider.metadata())
        bad["modelFingerprint"] = "wrong"
        with pytest.raises(Exception, match="MODEL_FINGERPRINT_MISMATCH"):
            index.activate(manifest.indexVersion, bad, tenant_id="tenant-a")
    finally:
        provider.close()


@pytest.mark.real_dense
@pytest.mark.requires_model_asset
def test_v200_phase3a_real_dense_and_hybrid_e2e_runtime(tmp_path):
    model_path = os.getenv("RAG_BGE_M3_MODEL_PATH", "")
    if not model_path:
        pytest.skip("MODEL_ASSET_UNAVAILABLE_SKIP")
    provider = BgeM3EmbeddingProvider(BgeM3ProviderConfig(model_path=Path(model_path), device=os.getenv("RAG_BGE_M3_DEVICE", "cpu"), batch_size=4, max_length=128, normalize=True))
    index = FaissVectorIndex(tmp_path / "runtime-faiss")
    try:
        chunks = _chunks()[:30]
        manifest = index.build(chunks=chunks, provider=provider, tenant_id="tenant-a", index_version="runtime-v1")
        index.activate(manifest.indexVersion, provider.metadata(), tenant_id="tenant-a")
        runtime = GovernedHybridRuntime(chunks=chunks, provider=provider, faiss_index=index, real_dense_required=True)
        dense_hits, dense_trace = runtime.search("refund broken after-sales", tenant_id="tenant-a", mode="real-dense", fusion_top_k=3)
        hybrid_hits, hybrid_trace = runtime.search("unsafe smoke fire", tenant_id="tenant-a", mode="hybrid-real", fusion_top_k=3)
        assert dense_hits
        assert hybrid_hits
        assert dense_trace.effectiveRetrievalMode == "real-dense"
        assert hybrid_trace.effectiveRetrievalMode == "hybrid-real"
        assert dense_trace.faissSearchDurationNs > 0
    finally:
        provider.close()


@pytest.mark.real_dense
@pytest.mark.requires_model_asset
def test_v200_phase3a_model_unavailable_fallback_after_real_mode_request():
    runtime = GovernedHybridRuntime(chunks=_chunks(), provider=DisabledEmbeddingProvider("MODEL_MISSING"), fallback_provider="hash", real_dense_required=False)
    candidates, trace = runtime.search("refund broken", tenant_id="tenant-a", mode="hybrid-real", fusion_top_k=5)
    assert candidates
    assert trace.denseFallbackUsed is True
    assert trace.effectiveRetrievalMode == "hybrid-hash"
