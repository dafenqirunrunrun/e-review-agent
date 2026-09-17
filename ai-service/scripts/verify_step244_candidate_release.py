from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.document_ingestion.candidate_index import PolicyIndexReleaseStore, build_candidate
from app.document_ingestion.models import DocumentNode, NormalizedDocument
from app.policy_rag.reflection import PolicyReflectionEngine
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.rag.document_contract import stable_hash


def _request(root: Path, version: str, marker: str) -> Path:
    documents = root / "documents"
    normalized_path = documents / "policy-doc" / "lease" / "normalized.json"
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    markdown = (
        "# 平台评价治理规则\n\n"
        f"## 评价真实性\n\n不得通过现金奖励诱导五星评价，也不得组织刷单。版本标记{marker}。\n\n"
        "## 评价展示\n\n不得删除差评或压制消费者真实评价。\n\n"
        "## 售后保障\n\n退款、退货和商品破损投诉应保留售后处理证据。\n"
    )
    document = NormalizedDocument(
        documentId="policy-doc",
        sourceName="隔离验证政策",
        sourceType="uploaded_document",
        sourceUri="https://example.org/e-review-policy",
        format="markdown",
        mimeType="text/markdown",
        language="zh",
        parser="lightweight",
        parserVersion="step24.4-verification",
        contentHash=stable_hash(markdown),
        markdown=markdown,
        nodes=[DocumentNode(
            nodeId="verification-node-01",
            type="paragraph",
            order=0,
            text=markdown,
            sectionPath=["平台评价治理规则"],
            sourceRef="#/nodes/0",
        )],
        metadata={"fileHash": "a" * 64},
    )
    normalized_path.write_text(document.model_dump_json(), encoding="utf-8")
    request = root / f"{version}.json"
    request.write_text(json.dumps({
        "releaseId": version[-8:],
        "version": version,
        "documentRoot": str(documents),
        "indexRoot": str(root / "managed"),
        "baseIndexPath": str(root / "empty-base.jsonl"),
        "denseRequired": True,
        "documents": [{
            "documentId": "policy-doc",
            "resultPath": "policy-doc/lease/normalized.json",
            "sourceName": "隔离验证政策",
            "sourceUrl": "https://example.org/e-review-policy",
            "fileHash": "a" * 64,
        }],
    }, ensure_ascii=False), encoding="utf-8")
    return request


def main() -> int:
    started = time.perf_counter()
    first_version = "policy-20260915T150000-11111111"
    second_version = "policy-20260915T150100-22222222"
    with tempfile.TemporaryDirectory(prefix="e-review-step244-") as temporary:
        root = Path(temporary)
        store = PolicyIndexReleaseStore(root / "managed")
        first = build_candidate(_request(root, first_version, "甲"))
        pre_publish_invisible = store.active_version() is None
        store.publish(first_version)
        os.environ["E_REVIEW_POLICY_RAG_MANAGED_INDEX_ROOT"] = str(root / "managed")
        retriever = PolicyEvidenceRetriever()
        first_hits = retriever.search("评价后给现金奖励", risk_hints=["rating_manipulation"], top_k=5, mode="hybrid")
        reflection = PolicyReflectionEngine().reflect(
            risk_level="high",
            risk_types=["rating_manipulation"],
            confidence=0.95,
            policy_evidence=first_hits,
        )

        second = build_candidate(_request(root, second_version, "乙"))
        second_invisible = not any("版本标记乙" in item.snippet for item in retriever.search("版本标记乙", top_k=5, mode="bm25"))
        store.publish(second_version)
        second_hits = retriever.search("版本标记乙", top_k=5, mode="hybrid")
        store.rollback(first_version)
        rollback_hits = retriever.search("版本标记甲", top_k=5, mode="bm25")
        checks = {
            "firstCandidatePassed": first["gate"] == "PASS",
            "secondCandidatePassed": second["gate"] == "PASS",
            "prePublishInvisible": pre_publish_invisible,
            "unpublishedSecondInvisible": second_invisible,
            "hybridAvailable": bool(first_hits) and all(item.retrieval.get("mode") == "hybrid" for item in first_hits),
            "publishedSecondVisible": any("版本标记乙" in item.snippet for item in second_hits),
            "rollbackRestoredFirst": any("版本标记甲" in item.snippet for item in rollback_hits),
            "activePointerRolledBack": store.active_version() == first_version,
            "citationValid": all(item.sourceName and item.sourceUrl and item.sectionPath and item.contentHash for item in first_hits),
            "reflectionAcceptsUploadedPolicy": reflection.passed and reflection.evidenceStatus == "supported",
        }
        report = {
            "schemaVersion": "step24.4-candidate-index-verification-v1",
            "gate": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "first": {"version": first_version, "chunks": first["chunkCount"], "dense": first["dense"]},
            "second": {"version": second_version, "chunks": second["chunkCount"], "dense": second["dense"]},
            "activeAfterRollback": store.active_version(),
            "elapsedMs": round((time.perf_counter() - started) * 1000, 3),
        }
    output = ROOT / "artifacts" / "step244" / "candidate_index_verification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
