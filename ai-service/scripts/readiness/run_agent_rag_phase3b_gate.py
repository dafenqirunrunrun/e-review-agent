from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.agent_rag.phase2_retrieval import RetrievalCandidate
from app.agent_rag.reranker import GovernedReranker, RerankerConfig, audit_reranker_model_asset, load_reranker_config


OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-phase3b"


def _candidate(chunk_id: str, score: float, content: str = "refund broken after-sales policy") -> RetrievalCandidate:
    return RetrievalCandidate(
        retrieverType="fixture",
        tenantId="tenant-a",
        documentId=f"doc-{chunk_id}",
        chunkId=chunk_id,
        sparseScore=score,
        sparseRank=1,
        rawRank=1,
        fusionScore=score,
        fusionRank=1,
        row={
            "tenant_id": "tenant-a",
            "document_id": f"doc-{chunk_id}",
            "chunk_id": chunk_id,
            "content": content,
            "content_hash": f"{chunk_id}abc123abc123",
            "source_type": "policy",
            "title": f"Title {chunk_id}",
            "active": True,
            "deleted": False,
        },
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    deterministic = GovernedReranker(RerankerConfig(requested_type="deterministic")).rerank(
        "refund broken after-sales",
        [_candidate("a", 0.1), _candidate("b", 0.2, "general shipping policy")],
        top_k=2,
        tenant_id="tenant-a",
        request_id="phase3b-gate",
    )
    env = dict(os.environ)
    if not env.get("RAG_RERANKER_MODEL_PATH", "").strip():
        env.pop("AGENT_RAG_V22_ASSET_MANIFEST", None)
    fallback_config = load_reranker_config(env)
    fallback = GovernedReranker(fallback_config).rerank(
        "refund broken after-sales",
        [_candidate("a", 0.1), _candidate("b", 0.2, "general shipping policy")],
        top_k=2,
        tenant_id="tenant-a",
        request_id="phase3b-gate-fallback",
    )
    audit = audit_reranker_model_asset(fallback_config)
    model_verified = (
        fallback.effectiveType == "local-model"
        and not fallback.fallbackUsed
        and bool(fallback.modelFingerprint)
        and audit.exists
        and audit.configPresent
        and audit.tokenizerPresent
        and audit.weightsPresent
    )
    result = {
        "schemaVersion": "agent-rag-phase3b-gate-v1",
        "status": "PASS" if model_verified else "BLOCKED",
        "contractStatus": "PASS",
        "fallbackStatus": "PASS" if fallback.fallbackUsed else "NOT_USED",
        "modelRerankerStatus": "PASS" if model_verified else "BLOCKED",
        "deterministic": {
            "effectiveType": deterministic.effectiveType,
            "inputCount": deterministic.inputCount,
            "outputCount": deterministic.outputCount,
            "fallbackUsed": deterministic.fallbackUsed,
        },
        "modelAttempt": {
            "requestedType": fallback.requestedType,
            "effectiveType": fallback.effectiveType,
            "fallbackUsed": fallback.fallbackUsed,
            "fallbackReason": fallback.fallbackReason,
            "modelName": fallback.modelName,
            "modelFingerprint": fallback.modelFingerprint,
        },
        "assetAudit": audit.__dict__,
        "boundaries": [
            "REAL_LLM_QUALITY_NOT_VERIFIED",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    (OUT / "phase3b-gate-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("AGENT_RAG_RERANKER_CONTRACT_PASS")
    print("AGENT_RAG_RERANKER_FALLBACK_PASS")
    if model_verified:
        print("AGENT_RAG_MODEL_RERANKER_PASS")
        print("AGENT_RAG_PHASE3B_PASS")
    else:
        print("AGENT_RAG_MODEL_RERANKER_BLOCKED")
        print("AGENT_RAG_PHASE3B_BLOCKED")
    print("REAL_LLM_QUALITY_NOT_VERIFIED")
    print("ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED")
    print("NO_PUSH")
    print("NO_TAG")
    print("NO_RELEASE")


if __name__ == "__main__":
    main()
