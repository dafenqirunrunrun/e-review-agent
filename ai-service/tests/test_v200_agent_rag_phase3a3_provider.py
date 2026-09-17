import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.agent_rag.embedding_provider import BgeM3EmbeddingProvider, BgeM3ProviderConfig, HashEmbeddingProvider, OfficialBgeM3FlagProvider, SentenceTransformerBgeM3Provider
from app.agent_rag.faiss_index import FaissVectorIndex, IndexCompatibilityError
from app.agent_rag.phase3a_retrieval import make_bge_m3_provider

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ai-service" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from agent_rag_phase3a_common import phase3a_chunks


def test_v200_phase3a3_legacy_metadata_and_fingerprints():
    model_path = os.getenv("RAG_BGE_M3_MODEL_PATH", "")
    if not model_path:
        pytest.skip("MODEL_ASSET_UNAVAILABLE_SKIP")
    provider = BgeM3EmbeddingProvider(BgeM3ProviderConfig(model_path=Path(model_path), device="cpu", batch_size=1, max_length=64, normalize=True))
    try:
        provider.embed_query("metadata probe")
        meta = provider.metadata()
        assert meta["providerType"] == "bge-m3-legacy-cls"
        assert meta["providerImpl"] == "legacy-cls"
        assert meta["providerConformance"] == "legacy-experimental"
        assert meta["assetFingerprint"]
        assert meta["providerFingerprint"]
        assert meta["effectiveEmbeddingFingerprint"]
        assert str(Path(model_path)) not in json.dumps(meta)
    finally:
        provider.close()


def test_v200_phase3a3_provider_factory_routes_impls():
    legacy = make_bge_m3_provider(provider_impl="legacy-cls", model_path="__missing__")
    flag = make_bge_m3_provider(provider_impl="flagembedding", model_path="__missing__")
    st = make_bge_m3_provider(provider_impl="sentence-transformers", model_path="__missing__")
    assert isinstance(legacy, BgeM3EmbeddingProvider)
    assert isinstance(flag, OfficialBgeM3FlagProvider)
    assert isinstance(st, SentenceTransformerBgeM3Provider)
    with pytest.raises(ValueError, match="RAG_BGE_M3_PROVIDER_IMPL_UNSUPPORTED"):
        make_bge_m3_provider(provider_impl="bad", model_path="__missing__")


def test_v200_phase3a3_missing_model_is_explicit():
    provider = OfficialBgeM3FlagProvider(BgeM3ProviderConfig(model_path=Path("__missing__")))
    with pytest.raises(RuntimeError, match="MODEL_ASSET_NOT_FOUND"):
        provider.embed_query("probe")


def test_v200_phase3a3_flag_dependency_missing_or_metadata_real():
    model_path = os.getenv("RAG_BGE_M3_MODEL_PATH", "")
    if not model_path:
        pytest.skip("MODEL_ASSET_UNAVAILABLE_SKIP")
    provider = OfficialBgeM3FlagProvider(BgeM3ProviderConfig(model_path=Path(model_path), device="cpu", batch_size=1, max_length=64))
    try:
        try:
            provider.embed_query("dependency probe")
        except RuntimeError as exc:
            assert "PROVIDER_DEPENDENCY_MISSING:FlagEmbedding" in str(exc)
        else:
            meta = provider.metadata()
            assert meta["providerImpl"] == "flagembedding"
            assert meta["encodeMethod"] == "BGEM3FlagModel.encode.dense_vecs"
            assert meta["dimension"] == 1024
    finally:
        provider.close()


def test_v200_phase3a3_fingerprint_differs_between_hash_and_legacy():
    model_path = os.getenv("RAG_BGE_M3_MODEL_PATH", "")
    if not model_path:
        pytest.skip("MODEL_ASSET_UNAVAILABLE_SKIP")
    legacy = BgeM3EmbeddingProvider(BgeM3ProviderConfig(model_path=Path(model_path), device="cpu", batch_size=1, max_length=64))
    try:
        legacy.embed_query("fingerprint probe")
        hash_meta = HashEmbeddingProvider().metadata()
        legacy_meta = legacy.metadata()
        assert hash_meta["effectiveEmbeddingFingerprint"] != legacy_meta["effectiveEmbeddingFingerprint"]
    finally:
        legacy.close()


def test_v200_phase3a3_index_rejects_provider_impl_mismatch(tmp_path):
    model_path = os.getenv("RAG_BGE_M3_MODEL_PATH", "")
    if not model_path:
        pytest.skip("MODEL_ASSET_UNAVAILABLE_SKIP")
    provider = BgeM3EmbeddingProvider(BgeM3ProviderConfig(model_path=Path(model_path), device="cpu", batch_size=2, max_length=64))
    try:
        chunks = phase3a_chunks("tenant-a")[1][:8]
        index = FaissVectorIndex(tmp_path / "faiss")
        manifest = index.build(chunks=chunks, provider=provider, tenant_id="tenant-a", index_version="legacy-v1")
        bad = dict(provider.metadata())
        bad["providerImpl"] = "flagembedding"
        with pytest.raises(IndexCompatibilityError, match="PROVIDER_IMPL_MISMATCH"):
            index.activate(manifest.indexVersion, bad, tenant_id="tenant-a")
    finally:
        provider.close()


def test_v200_phase3a3_sanity_script_records_blocked_reference():
    completed = subprocess.run([sys.executable, "ai-service/scripts/diagnostics/run_bge_m3_provider_sanity.py"], cwd=ROOT, text=True, capture_output=True, check=True)
    payload = json.loads(completed.stdout)
    assert "legacy-cls" in payload["providers"]
    assert "flagembedding" in payload["providers"]
    assert payload["providers"]["flagembedding"]["status"] in {"PASS", "BLOCKED"}


@pytest.mark.bge_reference
def test_v200_phase3a3_sentence_transformers_reference_marker():
    provider = SentenceTransformerBgeM3Provider(BgeM3ProviderConfig(model_path=Path(os.getenv("RAG_BGE_M3_MODEL_PATH", "__missing__"))))
    try:
        try:
            provider.embed_query("reference probe")
        except RuntimeError as exc:
            assert (
                "PROVIDER_DEPENDENCY_MISSING:sentence-transformers" in str(exc)
                or "MODEL_ASSET_NOT_FOUND" in str(exc)
                or "REFERENCE_PROVIDER_COMPATIBILITY_BLOCKED" in str(exc)
            )
        else:
            assert provider.metadata()["providerImpl"] == "sentence-transformers"
    finally:
        provider.close()
