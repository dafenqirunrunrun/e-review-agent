from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from app.document_ingestion.candidate_index import PolicyIndexReleaseStore, build_candidate
from app.document_ingestion.models import DocumentNode, NormalizedDocument
from app.policy_rag.index_store import load_policy_chunks
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.rag.document_contract import stable_hash


class FakeEmbeddingProvider:
    provider_type = "fake-test"

    def __init__(self):
        self.embedded_text_count = 0

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        self.embedded_text_count += len(texts)
        rows = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vector = np.asarray([byte + 1 for byte in digest[:8]], dtype="float32")
            rows.append(vector / np.linalg.norm(vector))
        return np.asarray(rows, dtype="float32")

    def embed_query(self, text: str) -> np.ndarray:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector = np.asarray([byte + 1 for byte in digest[:8]], dtype="float32")
        return np.asarray([vector / np.linalg.norm(vector)], dtype="float32")

    def metadata(self) -> dict:
        return {"providerType": self.provider_type, "modelName": "fake", "dimension": 8, "normalize": True}

    def health(self) -> dict:
        return {"status": "ready", "loaded": True, "reason": ""}


class FailingEmbeddingProvider(FakeEmbeddingProvider):
    def embed_documents(self, texts: list[str]) -> np.ndarray:
        raise RuntimeError("TEST_DENSE_UNAVAILABLE")


def _request(tmp_path: Path, version: str, text: str) -> Path:
    document_root = tmp_path / "documents"
    result = document_root / "doc-1" / "lease" / "normalized.json"
    result.parent.mkdir(parents=True, exist_ok=True)
    markdown = (
        "# 评价治理规则\n\n"
        f"## 唯一规则\n\n{text}\n\n"
        "## 评价压制\n\n不得删除差评或压制真实负面评价。\n\n"
        "## 售后处理\n\n退款、退货和破损售后投诉应当保留证据。\n"
    )
    document = NormalizedDocument(
        documentId="doc-1",
        sourceName="测试政策",
        sourceType="uploaded_document",
        sourceUri="https://example.org/policy",
        format="markdown",
        mimeType="text/markdown",
        language="zh",
        parser="lightweight",
        parserVersion="test-v1",
        contentHash=stable_hash(markdown),
        markdown=markdown,
        nodes=[DocumentNode(nodeId="test-node-0001", type="paragraph", order=0, text=markdown, sectionPath=["评价治理规则"], sourceRef="#/nodes/0")],
        metadata={"fileHash": "a" * 64},
    )
    result.write_text(document.model_dump_json(), encoding="utf-8")
    request = tmp_path / f"{version}.json"
    request.write_text(json.dumps({
        "releaseId": version[-8:],
        "version": version,
        "documentRoot": str(document_root),
        "indexRoot": str(tmp_path / "managed"),
        "baseIndexPath": str(tmp_path / "missing.jsonl"),
        "denseRequired": True,
        "documents": [{
            "documentId": "doc-1",
            "resultPath": "doc-1/lease/normalized.json",
            "sourceName": "测试政策",
            "sourceUrl": "https://example.org/policy",
            "fileHash": "a" * 64,
        }],
    }, ensure_ascii=False), encoding="utf-8")
    return request


def _multi_request(tmp_path: Path, version: str, documents: list[tuple[str, str, str]], *, allow_empty: bool = False) -> Path:
    document_root = tmp_path / "documents"
    request_documents = []
    for document_id, source_url, marker in documents:
        result = document_root / document_id / "lease" / "normalized.json"
        result.parent.mkdir(parents=True, exist_ok=True)
        markdown = (
            "# 评价治理规则\n\n"
            f"## {marker}\n\n禁止刷单、好评返现和评分操纵，版本标记{marker}。\n\n"
            "## 评价压制\n\n不得删除差评或压制真实负面评价。\n\n"
            "## 售后处理\n\n退款、退货和破损售后投诉应当保留证据。\n"
        )
        file_hash = hashlib.sha256(f"{document_id}:{marker}".encode()).hexdigest()
        document = NormalizedDocument(
            documentId=document_id,
            sourceName=f"测试政策-{source_url.rsplit('/', 1)[-1]}",
            sourceType="uploaded_document",
            sourceUri=source_url,
            format="markdown",
            mimeType="text/markdown",
            language="zh",
            parser="lightweight",
            parserVersion="test-v1",
            contentHash=stable_hash(markdown),
            markdown=markdown,
            nodes=[DocumentNode(nodeId=f"{document_id}-node", type="paragraph", order=0, text=markdown, sourceRef="#/nodes/0")],
            metadata={"fileHash": file_hash},
        )
        result.write_text(document.model_dump_json(), encoding="utf-8")
        request_documents.append({
            "documentId": document_id,
            "resultPath": f"{document_id}/lease/normalized.json",
            "sourceName": document.sourceName,
            "sourceUrl": source_url,
            "fileHash": file_hash,
        })
    request = tmp_path / f"{version}.json"
    request.write_text(json.dumps({
        "releaseId": version[-8:],
        "version": version,
        "documentRoot": str(document_root),
        "indexRoot": str(tmp_path / "managed"),
        "baseIndexPath": str(tmp_path / "missing.jsonl"),
        "denseRequired": True,
        "allowEmptyUploads": allow_empty,
        "documents": request_documents,
    }, ensure_ascii=False), encoding="utf-8")
    return request


def test_candidate_publish_hot_reload_and_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("faiss")
    root = tmp_path / "managed"
    first_version = "policy-20260915T120000-aaaaaaaa"
    second_version = "policy-20260915T120100-bbbbbbbb"
    first = build_candidate(_request(tmp_path, first_version, "禁止刷单和好评返现，暗号甲。"), embedding_provider=FakeEmbeddingProvider())
    assert first["gate"] == "PASS"
    assert not (root / "ACTIVE").exists()

    store = PolicyIndexReleaseStore(root)
    store.publish(first_version)
    monkeypatch.setenv("E_REVIEW_POLICY_RAG_MANAGED_INDEX_ROOT", str(root))
    retriever = PolicyEvidenceRetriever()
    first_hits = retriever.search("暗号甲", top_k=3, mode="bm25")
    assert any("暗号甲" in item.snippet for item in first_hits)
    assert all(item.sourceType == "policy" for item in first_hits)

    second = build_candidate(_request(tmp_path, second_version, "禁止刷单和好评返现，暗号乙。"), embedding_provider=FakeEmbeddingProvider())
    assert second["gate"] == "PASS"
    assert not any("暗号乙" in item.snippet for item in retriever.search("暗号乙", top_k=3, mode="bm25"))
    store.publish(second_version)
    assert any("暗号乙" in item.snippet for item in retriever.search("暗号乙", top_k=3, mode="bm25"))

    store.rollback(first_version)
    assert any("暗号甲" in item.snippet for item in retriever.search("暗号甲", top_k=3, mode="bm25"))
    assert retriever.readiness()["activeVersion"] == first_version


def test_incremental_candidate_replaces_same_source_removes_deleted_source_and_reuses_vectors(tmp_path: Path) -> None:
    pytest.importorskip("faiss")
    store = PolicyIndexReleaseStore(tmp_path / "managed")
    first_version = "policy-20260916T100000-11111111"
    second_version = "policy-20260916T100100-22222222"
    first_provider = FakeEmbeddingProvider()
    first = build_candidate(_multi_request(tmp_path, first_version, [
        ("doc-a-v1", "https://example.org/policy/a", "甲旧"),
        ("doc-b-v1", "https://example.org/policy/b", "乙保留"),
    ]), embedding_provider=first_provider)
    assert first["gate"] == "PASS"
    store.publish(first_version)

    second_provider = FakeEmbeddingProvider()
    second = build_candidate(_multi_request(tmp_path, second_version, [
        ("doc-a-v2", "https://example.org/policy/a", "甲新"),
    ]), embedding_provider=second_provider)
    chunks = load_policy_chunks(tmp_path / "managed" / "versions" / f"{second_version}.staging" / "policy_chunks.jsonl")
    text = "\n".join(chunk.text for chunk in chunks)

    assert second["gate"] == "PASS"
    assert "甲新" in text
    assert "甲旧" not in text
    assert "乙保留" not in text
    assert second["incremental"]["reusedVectorCount"] > 0
    assert second["incremental"]["embeddedVectorCount"] < second["chunkCount"]
    assert second_provider.embedded_text_count == second["incremental"]["embeddedVectorCount"]


def test_dense_failure_blocks_candidate_publication(tmp_path: Path) -> None:
    pytest.importorskip("faiss")
    version = "policy-20260915T130000-cccccccc"
    result = build_candidate(_request(tmp_path, version, "禁止刷单和好评返现。"), embedding_provider=FailingEmbeddingProvider())
    assert result["gate"] == "FAIL"
    assert result["checks"]["denseReady"] is False
    with pytest.raises(ValueError, match="INDEX_QUALITY_GATE_NOT_PASSED"):
        PolicyIndexReleaseStore(tmp_path / "managed").publish(version)


def test_checksum_tamper_blocks_publication(tmp_path: Path) -> None:
    pytest.importorskip("faiss")
    version = "policy-20260915T140000-dddddddd"
    result = build_candidate(_request(tmp_path, version, "禁止刷单和好评返现。"), embedding_provider=FakeEmbeddingProvider())
    assert result["gate"] == "PASS"
    chunks = tmp_path / "managed" / "versions" / f"{version}.staging" / "policy_chunks.jsonl"
    chunks.write_text(chunks.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="INDEX_ARTIFACT_CHECKSUM_MISMATCH"):
        PolicyIndexReleaseStore(tmp_path / "managed").publish(version)


def test_first_publish_can_be_compensated_and_retried(tmp_path: Path) -> None:
    pytest.importorskip("faiss")
    version = "policy-20260915T150000-eeeeeeee"
    assert build_candidate(_request(tmp_path, version, "禁止刷单和好评返现。"), embedding_provider=FakeEmbeddingProvider())["gate"] == "PASS"
    store = PolicyIndexReleaseStore(tmp_path / "managed")
    store.publish(version)
    assert store.deactivate(version)["active"] is False
    assert store.active_version() is None
    assert store.publish(version)["active"] is True


def test_candidate_purifies_noise_compacts_short_paragraphs_and_infers_source_metadata(tmp_path: Path) -> None:
    pytest.importorskip("faiss")
    document_root = tmp_path / "documents"
    result = document_root / "ftc-doc" / "lease" / "normalized.json"
    result.parent.mkdir(parents=True, exist_ok=True)
    markdown = (
        "# Consumer Review Rule\n\n"
        "## Controls\n\nBack to top\n\n"
        "Print this page\n\n"
        "This first short paragraph provides useful context for the consumer review regulation.\n\n"
        "This adjacent paragraph explains how the regulation applies to consumer reviews.\n\n"
        "## § 465.4 Incentivized reviews\n\n"
        "§ 465.4 Businesses must not condition compensation on positive review sentiment.\n"
    )
    document = NormalizedDocument(
        documentId="ftc-doc",
        sourceName="FTC Consumer Review Rule",
        sourceType="uploaded_document",
        sourceUri="https://www.ftc.gov/legal-library/browse/rules/consumer-reviews-testimonials-rule",
        format="html",
        mimeType="text/html",
        language="und",
        parser="lightweight",
        parserVersion="stdlib-v2",
        contentHash=stable_hash(markdown),
        markdown=markdown,
        nodes=[DocumentNode(nodeId="ftc-node-0001", type="paragraph", order=0, text=markdown, sourceRef="html:main")],
        metadata={"fileHash": "b" * 64},
    )
    document.model_dump_json()
    result.write_text(document.model_dump_json(), encoding="utf-8")
    request = tmp_path / "candidate.json"
    request.write_text(json.dumps({
        "releaseId": "ffffffff",
        "version": "policy-20260916T010000-ffffffff",
        "documentRoot": str(document_root),
        "indexRoot": str(tmp_path / "managed"),
        "baseIndexPath": str(tmp_path / "missing.jsonl"),
        "denseRequired": True,
        "documents": [{
            "documentId": "ftc-doc",
            "resultPath": "ftc-doc/lease/normalized.json",
            "sourceName": "FTC Consumer Review Rule",
            "sourceUrl": document.sourceUri,
            "fileHash": "b" * 64,
        }],
    }), encoding="utf-8")

    manifest = build_candidate(request, embedding_provider=FakeEmbeddingProvider())
    chunks_path = tmp_path / "managed" / "versions" / "policy-20260916T010000-ffffffff.staging" / "policy_chunks.jsonl"
    chunks = [json.loads(line) for line in chunks_path.read_text(encoding="utf-8").splitlines()]

    # This fixture intentionally contains only one FTC rule. The index itself is
    # valid, but the operational release suite must block it because the other
    # business risk families have no supporting evidence.
    assert manifest["gate"] == "FAIL"
    assert manifest["dense"]["status"] == "ready"
    assert manifest["releaseEvaluation"]["decision"] == "blocked"
    assert "CRITICAL_RISK_EVIDENCE_MISSING" in manifest["releaseEvaluation"]["reasonCodes"]
    assert manifest["sources"][0]["sourceType"] == "regulation"
    assert manifest["sources"][0]["jurisdiction"] == "US"
    assert manifest["sources"][0]["language"] == "en"
    assert manifest["sources"][0]["parser"] == "lightweight_html"
    assert manifest["purification"]["droppedNoiseCount"] == 2
    assert manifest["purification"]["mergedChunkCount"] >= 1
    assert not any("Back to top" in chunk["text"] or "Print this page" in chunk["text"] for chunk in chunks)
    assert any(chunk["clauseId"] == "465.4" and chunk["metadata"]["contentTier"] == "A" for chunk in chunks)
