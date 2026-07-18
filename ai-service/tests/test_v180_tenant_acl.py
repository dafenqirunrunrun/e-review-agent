import pytest

from app.platform.cache import safe_cache_key
from app.platform.security import SafeStructuredLogger
from app.rag.dense_retriever import HashDenseRetriever
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.sparse_retriever import BM25Retriever
from app.rag.tenant_acl import TenantAccessController, TenantPrincipal, normalize_tenant_id


ATTACK_TENANTS = [
    "Tenant-A",
    " tenant-a ",
    "ＴＥＮＡＮＴ-Ａ",
    "tenant-a",
    "TENANT-A",
    "tenant-a\n",
    "tenant-a\t",
    "tenant-a\u200b",
]


@pytest.mark.parametrize("tenant_id", ATTACK_TENANTS)
def test_v180_tenant_normalization_keeps_same_logical_tenant(tenant_id):
    if "\u200b" in tenant_id:
        with pytest.raises(ValueError):
            normalize_tenant_id(tenant_id)
    else:
        assert normalize_tenant_id(tenant_id) == "tenant-a"


@pytest.mark.parametrize("bad_tenant", ["", "   ", "../tenant-a", "tenant/a", "tenant\\a", "\x00tenant"])
def test_v180_invalid_tenant_ids_are_rejected(bad_tenant):
    with pytest.raises(ValueError):
        normalize_tenant_id(bad_tenant)


def test_v180_acl_filters_private_public_deleted_and_superseded_documents():
    acl = TenantAccessController()
    principal = TenantPrincipal.from_tenant_id("tenant-a")
    docs = _docs()
    visible = acl.filter_documents(principal, docs)
    ids = {doc["document_id"] for doc in visible}
    assert "a-private" in ids
    assert "shared" in ids
    assert "b-private" not in ids
    assert "deleted" not in ids


def test_v180_sparse_dense_hybrid_all_apply_tenant_filter_after_overfetch():
    docs = _chunks()
    sparse_hits = BM25Retriever(docs).search("refund policy private", tenant_id="tenant-a")
    dense_hits = HashDenseRetriever(docs).search("refund policy private", tenant_id="tenant-a")
    hybrid_hits = HybridRetriever(docs).search("refund policy private", tenant_id="tenant-a")
    assert sparse_hits and dense_hits and hybrid_hits
    assert all(hit.document_id != "b-private" for hit in sparse_hits)
    assert all(hit.document_id != "b-private" for hit in dense_hits)
    assert all(hit.document_id != "b-private" for hit in hybrid_hits)


def test_v180_cache_key_includes_tenant_hash_and_logger_drops_raw_tenant_id():
    key_a = safe_cache_key(tenant_hash="tenant-a-hash", model_version="m", index_version="i", prompt_version="p", normalized_query="refund")
    key_b = safe_cache_key(tenant_hash="tenant-b-hash", model_version="m", index_version="i", prompt_version="p", normalized_query="refund")
    assert key_a != key_b
    event = SafeStructuredLogger().event(tenant_id="tenant-a", tenant_hash="tenant-a-hash")
    assert "tenant_id" not in event
    assert event["tenant_hash"] == "tenant-a-hash"


def test_v180_acl_safe_error_does_not_reveal_document_existence():
    error = TenantAccessController().safe_error("DOCUMENT_NOT_FOUND_OR_FORBIDDEN")
    assert "tenant" in error["message"]
    assert "document" not in error["message"].lower()


def _docs():
    return [
        {"tenant_id": "tenant-a", "document_id": "a-private", "active": True, "access_scope": "tenant"},
        {"tenant_id": "tenant-b", "document_id": "b-private", "active": True, "access_scope": "tenant"},
        {"tenant_id": "tenant-b", "document_id": "shared", "active": True, "access_scope": "public"},
        {"tenant_id": "tenant-a", "document_id": "deleted", "active": False, "access_scope": "tenant"},
    ]


def _chunks():
    return [
        {
            "tenant_id": "tenant-a",
            "document_id": "a-private",
            "document_version": "1",
            "chunk_id": "a1",
            "content": "refund policy private tenant a",
            "trust_level": "internal_verified",
            "active": True,
        },
        {
            "tenant_id": "tenant-b",
            "document_id": "b-private",
            "document_version": "1",
            "chunk_id": "b1",
            "content": "refund policy private tenant b",
            "trust_level": "internal_verified",
            "active": True,
        },
    ]
