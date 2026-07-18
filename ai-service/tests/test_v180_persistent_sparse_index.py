from app.rag.persistent_sparse_index import PersistentSparseIndex


def test_v180_persistent_sparse_restart_recovery_and_tenant_filter(tmp_path):
    chunks = [
        {
            "tenant_id": "tenant-a",
            "document_id": "doc-a",
            "document_version": "1",
            "chunk_id": "a1",
            "content": "refund broken product evidence",
            "trust_level": "internal_verified",
            "active": True,
        },
        {
            "tenant_id": "tenant-b",
            "document_id": "doc-b",
            "document_version": "1",
            "chunk_id": "b1",
            "content": "refund private tenant b policy",
            "trust_level": "internal_verified",
            "active": True,
        },
    ]
    index = PersistentSparseIndex(tmp_path / "sparse")
    manifest = index.build_staging(chunks)
    assert index.active_version() is None
    index.publish(manifest.index_version)

    restarted = PersistentSparseIndex(tmp_path / "sparse")
    retriever, loaded = restarted.load_active()
    assert loaded.chunk_count == 2
    hits = retriever.search("refund broken", tenant_id="tenant-a")
    assert hits
    assert all(hit.document_id != "doc-b" for hit in hits)


def test_v180_persistent_sparse_staging_cleanup_preserves_active(tmp_path):
    index = PersistentSparseIndex(tmp_path / "sparse")
    first = index.build_staging([
        {"tenant_id": "tenant-a", "document_id": "doc-a", "document_version": "1", "chunk_id": "a1", "content": "active policy"}
    ])
    index.publish(first.index_version)
    broken = index.versions / "broken.staging"
    broken.mkdir(parents=True)
    assert index.cleanup_staging() == 1
    assert index.active_version() == first.index_version
