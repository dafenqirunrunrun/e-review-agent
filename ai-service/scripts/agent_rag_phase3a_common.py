from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.agent_rag.knowledge import KnowledgeIngestionPipeline
from app.rag.document_contract import stable_hash


PHASE3A_OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-phase3a"


def source_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "local"


def model_path_from_env() -> str:
    return os.getenv("RAG_BGE_M3_MODEL_PATH", "").strip()


def provider_env() -> dict[str, Any]:
    return {
        "provider": os.getenv("RAG_DENSE_PROVIDER", "hash"),
        "modelPathConfigured": bool(model_path_from_env()),
        "device": os.getenv("RAG_BGE_M3_DEVICE", "cpu"),
        "batchSize": int(os.getenv("RAG_BGE_M3_BATCH_SIZE", "8")),
        "maxLength": int(os.getenv("RAG_BGE_M3_MAX_LENGTH", "512")),
        "normalize": os.getenv("RAG_BGE_M3_NORMALIZE", "true").lower() == "true",
        "loadOnStartup": os.getenv("RAG_BGE_M3_LOAD_ON_STARTUP", "false").lower() == "true",
        "fallbackProvider": os.getenv("RAG_DENSE_FALLBACK_PROVIDER", "hash"),
        "realDenseRequired": os.getenv("RAG_REAL_DENSE_REQUIRED", "false").lower() == "true",
    }


def phase3a_documents() -> list[dict[str, Any]]:
    tenants = ["tenant-a", "tenant-b", "tenant-c"]
    topics = [
        ("refund", "policy", "refund broken return after-sales customer service compensation seven day rule"),
        ("safety", "platform-rule", "unsafe smoke fire battery charger product safety escalation"),
        ("fraud", "risk-case", "fake counterfeit promotion invoice mismatch platform fraud handling"),
        ("logistics", "faq", "logistics delay slow parcel tracking warehouse dispatch rule"),
        ("manual", "product-manual", "product manual warranty usage temperature waterproof warning"),
        ("service", "customer-service", "customer service apology replacement coupon follow up"),
    ]
    docs: list[dict[str, Any]] = []
    for tenant in tenants:
        for topic, source_type, body in topics:
            for idx in range(3):
                content = " ".join([body, f"{tenant} scenario {idx}", "evidence clause"] * 14)
                docs.append(
                    {
                        "documentId": f"{tenant}-{topic}-{idx}",
                        "tenantId": tenant,
                        "sourceType": source_type,
                        "title": f"{tenant} {topic} governed knowledge {idx}",
                        "content": content,
                        "version": f"v{idx + 1}",
                        "contentHash": stable_hash(content),
                    }
                )
    public = [
        ("public-risk-taxonomy", "public-regulation", "public refund safety fraud logistics review governance taxonomy"),
        ("public-after-sales", "public-regulation", "public after sales return refund evidence retention guidance"),
        ("public-safety", "public-regulation", "public product safety fire smoke escalation guidance"),
    ]
    for doc_id, source_type, body in public:
        content = " ".join([body] * 12)
        docs.append(
            {
                "documentId": doc_id,
                "tenantId": "__public__",
                "sourceType": source_type,
                "title": doc_id,
                "content": content,
                "version": "v1",
                "visibility": "public",
                "contentHash": stable_hash(content),
            }
        )
    disabled = "disabled refund policy should never be retrieved"
    docs.append({"documentId": "tenant-a-disabled", "tenantId": "tenant-a", "sourceType": "policy", "title": "disabled", "content": disabled, "version": "v1", "status": "disabled", "contentHash": stable_hash(disabled)})
    expired = "expired refund policy should never be active"
    docs.append({"documentId": "tenant-a-expired", "tenantId": "tenant-a", "sourceType": "policy", "title": "expired", "content": expired, "version": "v1", "effectiveTo": "2020-01-01T00:00:00Z", "contentHash": stable_hash(expired)})
    return docs


def phase3a_chunks(tenant_id: str = "tenant-a"):
    return KnowledgeIngestionPipeline(chunk_max_tokens=24, chunk_overlap_tokens=2).ingest(phase3a_documents(), tenant_id=tenant_id, index_version="phase3a-fixture")


def phase3a_all_tenant_chunks():
    pipeline = KnowledgeIngestionPipeline(chunk_max_tokens=24, chunk_overlap_tokens=2)
    docs = phase3a_documents()
    chunks = []
    seen_chunks = set()
    summaries = {}
    for tenant in ["tenant-a", "tenant-b", "tenant-c"]:
        result, tenant_chunks = pipeline.ingest(docs, tenant_id=tenant, index_version=f"phase3a-fixture-{tenant}")
        summaries[tenant] = result.model_dump(mode="json")
        for chunk in tenant_chunks:
            if chunk.chunkId in seen_chunks:
                continue
            seen_chunks.add(chunk.chunkId)
            chunks.append(chunk)
    return {
        "tenantSummaries": summaries,
        "documentCount": len(docs),
        "chunkCount": len(chunks),
        "failedCount": sum(item["failedCount"] for item in summaries.values()),
    }, chunks


def phase3a_queries() -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    templates = [
        ("refund broken after-sales return", "refund"),
        ("unsafe smoke fire battery", "safety"),
        ("fake counterfeit promotion", "fraud"),
        ("logistics delay slow parcel", "logistics"),
        ("warranty product manual warning", "manual"),
        ("customer service replacement coupon", "service"),
        ("退货 refund 商品坏了", "refund"),
        ("起火 smoke 安全风险", "safety"),
        ("fake 虚假 promotion", "fraud"),
        ("物流 delay 太慢", "logistics"),
    ]
    for idx in range(120):
        text, expected = templates[idx % len(templates)]
        queries.append({"queryId": f"q-{idx:03d}", "tenantId": "tenant-a", "query": f"{text} case {idx}", "expectedTopic": expected})
    return queries


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
