from __future__ import annotations

import threading
from pathlib import Path

from app.agentic_workflow.workflow import AgenticReviewWorkflow
from app.policy_rag.models import PolicyChunk
from app.policy_rag.playground import PolicyEvidencePlayground
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.services.mock_analyzer import MockAnalyzer


def _chunk(marker: str) -> PolicyChunk:
    return PolicyChunk(
        chunkId=f"policy-runtime-{marker}-001",
        documentId=f"document-{marker}",
        sourceName=f"政策-{marker}",
        sourceUrl=f"https://example.org/{marker}",
        sourceType="regulation",
        heading="评价治理",
        sectionPath=["评价治理", marker],
        text=f"这是 {marker} 版本的唯一规则。",
        riskTypes=["rating_manipulation"],
        evidenceTags=["rating_manipulation"],
        contentHash=(marker * 16)[:16],
        tokenCount=8,
    )


def _managed_retriever(root: Path) -> PolicyEvidenceRetriever:
    retriever = PolicyEvidenceRetriever(chunks=[_chunk("base")])
    retriever._managed_enabled = True
    retriever._managed_root_override = root
    return retriever


def test_runtime_retriever_is_shared_by_workflow_and_playground():
    workflow = AgenticReviewWorkflow(analyzer=MockAnalyzer())
    playground = PolicyEvidencePlayground()

    assert workflow.policy_retriever is playground.retriever


def test_hot_swap_is_single_flight_and_concurrent_queries_keep_old_index(tmp_path, monkeypatch):
    root = tmp_path / "managed"
    root.mkdir()
    version = "policy-20260917T120000-aaaaaaaa"
    (root / "ACTIVE").write_text(version, encoding="utf-8")
    retriever = _managed_retriever(root)
    candidate = PolicyEvidenceRetriever(chunks=[_chunk("candidate")])
    started = threading.Event()
    release = threading.Event()
    load_count = 0

    def load(_version: str):
        nonlocal load_count
        load_count += 1
        started.set()
        assert release.wait(timeout=5)
        return candidate

    monkeypatch.setattr(retriever, "_load_managed_version", load)
    first_result = []
    first = threading.Thread(target=lambda: first_result.extend(retriever.search("candidate", mode="bm25")))
    first.start()
    assert started.wait(timeout=5)

    old_result = retriever.search("base", mode="bm25")
    release.set()
    first.join(timeout=5)

    assert load_count == 1
    assert any("base" in item.snippet for item in old_result)
    assert any("candidate" in item.snippet for item in first_result)
    status = retriever.readiness()["runtimeIndex"]
    assert status["desiredIndexVersion"] == version
    assert status["loadedIndexVersion"] == version
    assert status["reloadStatus"] == "ready"
    assert status["loadedChunkCount"] == 1


def test_failed_reload_keeps_last_known_good_and_base_restore_is_atomic(tmp_path, monkeypatch):
    root = tmp_path / "managed"
    root.mkdir()
    first_version = "policy-20260917T120000-aaaaaaaa"
    broken_version = "policy-20260917T120100-bbbbbbbb"
    pointer = root / "ACTIVE"
    pointer.write_text(first_version, encoding="utf-8")
    retriever = _managed_retriever(root)
    candidate = PolicyEvidenceRetriever(chunks=[_chunk("candidate")])

    monkeypatch.setattr(retriever, "_load_managed_version", lambda _version: candidate)
    assert any("candidate" in item.snippet for item in retriever.search("candidate", mode="bm25"))

    pointer.write_text(broken_version, encoding="utf-8")

    def fail(_version: str):
        raise RuntimeError("BROKEN_CANDIDATE")

    monkeypatch.setattr(retriever, "_load_managed_version", fail)
    retained = retriever.search("candidate", mode="bm25")
    failed_status = retriever.readiness()["runtimeIndex"]

    assert any("candidate" in item.snippet for item in retained)
    assert failed_status["desiredIndexVersion"] == broken_version
    assert failed_status["loadedIndexVersion"] == first_version
    assert failed_status["reloadStatus"] == "failed"
    assert failed_status["lastReloadError"] == "POLICY_INDEX_RELOAD_FAILED"

    pointer.unlink()
    restored = retriever.search("base", mode="bm25")
    restored_status = retriever.readiness()["runtimeIndex"]

    assert any("base" in item.snippet for item in restored)
    assert restored_status["desiredIndexVersion"] == "base"
    assert restored_status["loadedIndexVersion"] == "base"
    assert restored_status["reloadStatus"] == "ready"
    assert restored_status["loadedChunkCount"] == 1
