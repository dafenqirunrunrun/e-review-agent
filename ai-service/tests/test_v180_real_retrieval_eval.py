import json
from pathlib import Path

import numpy as np
import pytest

from app.rag.versioned_faiss_index import VersionedFaissIndex


ROOT = Path(__file__).resolve().parents[2]


def test_v180_real_retrieval_eval_uses_real_bge_and_faiss():
    result = json.loads((ROOT / "data/private_research/eval/v180_real_retrieval_eval.json").read_text(encoding="utf-8"))
    assert result["status"] == "V180_REAL_RETRIEVAL_EVAL_PASS"
    assert result["real_bge_m3_used"] is True
    assert result["faiss_executed"] is True
    assert result["versioned_faiss_published"] is True
    assert result["persistent_restart_verified"] is True
    assert result["hash_dense_used_for_primary"] is False
    assert result["hash_dense_negative_control_only"] is True
    assert result["provider_metadata"]["provider"] == "bge_m3"
    assert result["index_manifest"]["dimension"] == 1024


def test_v180_real_retrieval_eval_records_hard_benchmark_metrics():
    result = json.loads((ROOT / "data/private_research/eval/v180_real_retrieval_eval.json").read_text(encoding="utf-8"))
    metrics = result["metrics"]
    assert metrics["hybrid_bge_m3_bm25_rrf"]["evaluated_positive_queries"] == 48
    assert metrics["hybrid_bge_m3_bm25_rrf"]["recall_at_5"] >= 0.5
    assert metrics["dense_bge_m3_faiss"]["recall_at_5"] >= metrics["hash_dense_negative_control"]["recall_at_5"]
    assert metrics["sparse_bm25"]["empty_retrieval_rate"] > 0


def test_v180_real_retrieval_eval_persistent_index_fixture_is_self_contained(tmp_path):
    pytest.importorskip("faiss")
    index_root = tmp_path / "faiss_index"
    store = VersionedFaissIndex(index_root)
    vectors = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype="float32",
    )
    metadata = [
        {"tenant_id": "tenant-a", "document_id": "doc-1", "chunk_id": "chunk-1"},
        {"tenant_id": "tenant-a", "document_id": "doc-2", "chunk_id": "chunk-2"},
        {"tenant_id": "tenant-b", "document_id": "doc-3", "chunk_id": "chunk-3"},
    ]

    staged = store.build_staging(
        vectors=vectors,
        metadata=metadata,
        embedding_model="fixture-bge-m3",
        embedding_hash="fixture-embedding-fingerprint",
    )
    published = store.publish(staged.index_version)
    index, loaded_metadata, loaded_manifest = store.load_active()

    assert store.active_version() == staged.index_version
    assert (index_root / "versions" / staged.index_version / "index.faiss").exists()
    assert (index_root / "versions" / staged.index_version / "metadata.jsonl").exists()
    assert (index_root / "versions" / staged.index_version / "manifest.json").exists()
    assert index.ntotal == len(metadata)
    assert loaded_metadata == metadata
    assert loaded_manifest.checksum == published.checksum
    assert loaded_manifest.embedding_hash == "fixture-embedding-fingerprint"
