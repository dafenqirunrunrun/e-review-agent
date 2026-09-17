import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent_rag.knowledge import KnowledgeDocument, KnowledgeIngestionPipeline, LocalIndexRegistry
from app.agent_rag.phase2_retrieval import (
    DeterministicReranker,
    EvidenceQualityGate,
    FailingModelReranker,
    QueryAnalyzer,
    RrfHybridRetriever,
)
from app.rag.document_contract import stable_hash


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "agent_rag" / "phase2" / "corpus.json"


def _docs():
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))["documents"]
    output = []
    for row in rows:
        item = dict(row)
        item["contentHash"] = stable_hash(item["content"])
        output.append(item)
    return output


def _chunks():
    _, chunks = KnowledgeIngestionPipeline().ingest(_docs(), tenant_id="tenant-a", index_version="test-v1")
    return chunks


def test_v200_phase2_document_schema_rejects_invalid_source_type_and_hash_dedup():
    with pytest.raises(ValidationError):
        KnowledgeDocument(documentId="bad", tenantId="tenant-a", sourceType="random", title="Bad", content="bad", version="1", contentHash="bad_hash_123456")
    doc = KnowledgeDocument.from_text(documentId="ok", tenantId="Tenant-A", sourceType="policy", title="Ok", content="same content", version="1")
    assert doc.tenantId == "tenant-a"
    assert doc.contentHash == stable_hash("same content")


def test_v200_phase2_chunking_filters_empty_and_deduplicates_content_hash():
    docs = [
        KnowledgeDocument.from_text(documentId="d1", tenantId="tenant-a", sourceType="policy", title="D1", content="refund broken evidence", version="1"),
        KnowledgeDocument.from_text(documentId="d2", tenantId="tenant-a", sourceType="policy", title="D2", content="refund broken evidence", version="1"),
        {"documentId": "empty", "tenantId": "tenant-a", "sourceType": "policy", "title": "Empty", "content": "", "status": "active", "version": "1", "contentHash": "empty_hash_123456"},
    ]
    result, chunks = KnowledgeIngestionPipeline().ingest(docs, tenant_id="tenant-a", index_version="dedup-v1")
    assert result.duplicateCount == 1
    assert result.failedCount == 1
    assert len(chunks) == 1


def test_v200_phase2_bm25_dense_and_hybrid_apply_tenant_filter():
    chunks = _chunks()
    for mode in ["sparse-only", "dense-only", "hybrid"]:
        candidates, counts = RrfHybridRetriever(chunks, mode=mode).search("tenant b refund private", tenant_id="tenant-a", fusion_top_k=5)
        assert counts["candidateCount"] >= 0
        assert all(candidate.tenantId in {"tenant-a", "__public__"} for candidate in candidates)
        assert all(candidate.documentId != "b-refund-v1" for candidate in candidates)


def test_v200_phase2_time_and_status_filter_exclude_expired_future_disabled():
    docs = [candidate.documentId for candidate in RrfHybridRetriever(_chunks()).search("future disabled refund", tenant_id="tenant-a", as_of_time="2026-07-19T00:00:00Z", fusion_top_k=10)[0]]
    assert "a-refund-v1" not in docs
    assert "public-future-v1" not in docs
    assert "a-disabled-v1" not in docs


def test_v200_phase2_query_analysis_expands_without_changing_original_fact():
    analysis = QueryAnalyzer().analyze("商品 refund broken 有异味", expansion_enabled=True, expansion_max=3)
    assert analysis.originalQuery.startswith("商品 refund")
    assert analysis.normalizedQuery in analysis.rewrittenQueries
    assert len(analysis.rewrittenQueries) <= 3
    assert analysis.riskIntent == "after_sales"


def test_v200_phase2_reranker_and_fallback_return_trace():
    candidates, _ = RrfHybridRetriever(_chunks()).search("refund broken evidence", tenant_id="tenant-a", fusion_top_k=5)
    reranked, trace = DeterministicReranker().rerank("refund broken evidence", candidates, 3)
    assert trace.rerankerType == "deterministic"
    assert trace.outputCount == len(reranked)
    fallback, fallback_trace = FailingModelReranker().rerank("refund broken evidence", candidates, 3)
    assert fallback_trace.fallbackUsed is True
    assert fallback


def test_v200_phase2_evidence_quality_rejects_cross_tenant_duplicate_and_missing_metadata():
    candidates, _ = RrfHybridRetriever(_chunks()).search("refund broken", tenant_id="tenant-a", fusion_top_k=5)
    accepted, quality = EvidenceQualityGate().filter(candidates, tenant_id="tenant-a")
    assert accepted
    assert all(row["accepted"] for row in quality)
    bad = candidates[0]
    bad = type(bad)(**{**bad.__dict__, "tenantId": "tenant-b"})
    accepted_bad, quality_bad = EvidenceQualityGate().filter([bad], tenant_id="tenant-a")
    assert not accepted_bad
    assert "cross-tenant" in quality_bad[0]["flags"]


def test_v200_phase2_index_manifest_activate_and_rollback():
    pipeline = KnowledgeIngestionPipeline()
    registry = LocalIndexRegistry()
    result_v1, chunks_v1 = pipeline.ingest(_docs(), tenant_id="tenant-a", index_version="idx-v1")
    registry.add_candidate(result_v1.manifest, chunks_v1)
    active_v1 = registry.activate_index("idx-v1")
    result_v2, chunks_v2 = pipeline.ingest(_docs(), tenant_id="tenant-a", index_version="idx-v2")
    registry.add_candidate(result_v2.manifest, chunks_v2)
    assert registry.active("tenant-a")[0].indexVersion == "idx-v1"
    active_v2 = registry.activate_index("idx-v2")
    rollback = registry.rollback_index("tenant-a", "idx-v1")
    assert active_v1.status == "active"
    assert active_v2.indexVersion == "idx-v2"
    assert rollback.indexVersion == "idx-v1"


def test_v200_phase2_scripts_generate_eval_lifecycle_and_gate_evidence():
    commands = [
        [sys.executable, "ai-service/scripts/evaluation/run_agent_rag_phase2_eval.py"],
        [sys.executable, "ai-service/scripts/e2e/run_agent_rag_index_lifecycle_e2e.py"],
        [sys.executable, "ai-service/scripts/readiness/run_agent_rag_phase2_gate.py"],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
        assert completed.stdout
    gate = json.loads((ROOT / "artifacts" / "agent-rag" / "v2.0-phase2" / "phase2-gate-result.json").read_text(encoding="utf-8"))
    assert gate["status"] == "PASS"
    assert gate["checks"]["indexRollback"] is True
