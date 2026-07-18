import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(AI_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_ROOT))

from app.rag.embedding_provider import BgeM3EmbeddingProvider, BgeM3EmbeddingProviderConfig, local_bge_m3_provider
from app.rag.versioned_faiss_index import VersionedFaissIndex


def test_v180_bge_provider_health_and_real_probe_if_available():
    provider = local_bge_m3_provider(device="cpu")
    health = provider.health_check()
    assert health["provider"] == "bge_m3"
    if not health["available"]:
        pytest.skip("local bge-m3 model is not available on this machine")
    vectors = provider.encode_documents(["same product quality", "unrelated refund policy"])
    query = provider.encode_queries(["same product quality"])
    metadata = provider.metadata()
    provider.close()
    assert vectors.dtype == np.float32
    assert query.dtype == np.float32
    assert vectors.shape[1] == metadata["dimension"] == 1024
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-4)
    assert metadata["model_hash"]


def test_v180_embedding_provider_rejects_zero_vectors(monkeypatch, tmp_path):
    provider = BgeM3EmbeddingProvider(BgeM3EmbeddingProviderConfig(model_dir=tmp_path))
    with pytest.raises(ValueError, match="ZERO_VECTOR"):
        provider._validate(np.zeros((1, 3), dtype="float32"))


@pytest.mark.skipif(importlib.util.find_spec("faiss") is None, reason="faiss not installed")
def test_v180_versioned_faiss_atomic_publish_load_and_rollback(tmp_path):
    index = VersionedFaissIndex(tmp_path / "faiss")
    metadata = [
        {"tenant_id": "tenant-a", "chunk_id": "c1", "document_id": "d1", "active": True},
        {"tenant_id": "tenant-a", "chunk_id": "c2", "document_id": "d2", "active": True},
    ]
    manifest = index.build_staging(np.eye(2, dtype="float32"), metadata, "BAAI/bge-m3", "abc123")
    assert index.active_version() is None
    published = index.publish(manifest.index_version)
    assert published.active is True
    loaded_index, rows, loaded_manifest = index.load_active()
    assert loaded_index.ntotal == 2
    assert rows[0]["chunk_id"] == "c1"
    assert loaded_manifest.checksum == published.checksum
    assert index.rollback(manifest.index_version).index_version == manifest.index_version


def test_v180_versioned_faiss_cleanup_staging(tmp_path):
    index = VersionedFaissIndex(tmp_path / "faiss")
    staging = index.versions / "broken.staging"
    staging.mkdir(parents=True)
    assert index.cleanup_staging() == 1
    assert not staging.exists()
