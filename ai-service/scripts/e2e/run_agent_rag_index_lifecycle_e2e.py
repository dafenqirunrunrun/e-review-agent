from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.agent_rag.knowledge import KnowledgeDocument, KnowledgeIngestionPipeline, LocalIndexRegistry
from app.agent_rag.phase2_retrieval import RrfHybridRetriever
from app.rag.document_contract import stable_hash
from scripts.evaluation.run_agent_rag_phase2_eval import OUT


def _doc(document_id: str, content: str, version: str = "1") -> dict:
    return {
        "documentId": document_id,
        "tenantId": "tenant-a",
        "sourceType": "policy",
        "title": document_id,
        "content": content,
        "status": "active",
        "version": version,
        "contentHash": stable_hash(content),
        "visibility": "tenant",
    }


def run() -> dict:
    pipeline = KnowledgeIngestionPipeline()
    registry = LocalIndexRegistry()
    result_v1, chunks_v1 = pipeline.ingest([_doc("refund-v1", "refund broken policy old active knowledge")], tenant_id="tenant-a", index_version="phase2-life-v1")
    registry.add_candidate(result_v1.manifest, chunks_v1)
    active_v1 = registry.activate_index("phase2-life-v1")
    _, active_chunks_v1 = registry.active("tenant-a")
    before_docs = _search_docs(active_chunks_v1, "refund broken")

    result_v2, chunks_v2 = pipeline.ingest([_doc("refund-v2", "refund broken policy new active knowledge plus photo evidence", "2")], tenant_id="tenant-a", index_version="phase2-life-v2")
    registry.add_candidate(result_v2.manifest, chunks_v2)
    _, still_v1_chunks = registry.active("tenant-a")
    before_activate_docs = _search_docs(still_v1_chunks, "photo evidence")
    active_v2 = registry.activate_index("phase2-life-v2")
    _, active_chunks_v2 = registry.active("tenant-a")
    after_activate_docs = _search_docs(active_chunks_v2, "photo evidence")
    rollback = registry.rollback_index("tenant-a", "phase2-life-v1")
    _, rollback_chunks = registry.active("tenant-a")
    rollback_docs = _search_docs(rollback_chunks, "refund broken")
    summary = {
        "schemaVersion": "agent-rag-index-lifecycle-e2e-v1",
        "completed": True,
        "v1ActiveVersion": active_v1.indexVersion,
        "v2ActiveVersion": active_v2.indexVersion,
        "rollbackVersion": rollback.indexVersion,
        "v1SearchOk": "refund-v1" in before_docs,
        "v2BeforeActivationDoesNotAffectV1": "refund-v2" not in before_activate_docs,
        "v2SearchOk": "refund-v2" in after_activate_docs,
        "rollbackSearchOk": "refund-v1" in rollback_docs and "refund-v2" not in rollback_docs,
        "manifestIndexVersionInEvidence": active_v2.indexVersion == "phase2-life-v2",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index-lifecycle-e2e.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def _search_docs(chunks, query: str) -> list[str]:
    candidates, _ = RrfHybridRetriever(chunks).search(query, tenant_id="tenant-a", fusion_top_k=5)
    return [candidate.documentId for candidate in candidates]


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
