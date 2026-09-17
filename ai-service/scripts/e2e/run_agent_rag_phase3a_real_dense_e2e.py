from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))
SCRIPTS = AI_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from agent_rag_phase3a_common import PHASE3A_OUT, model_path_from_env, phase3a_chunks, provider_env, source_commit, write_json
from app.agent_rag.embedding_provider import BgeM3EmbeddingProvider, BgeM3ProviderConfig, DisabledEmbeddingProvider
from app.agent_rag.faiss_index import FaissVectorIndex, IndexCompatibilityError
from app.agent_rag.phase3a_retrieval import GovernedHybridRuntime


def run() -> dict:
    env = provider_env()
    ingestion, chunks = phase3a_chunks("tenant-a")
    result = {"schemaVersion": "agent-rag-phase3a-e2e-v1", "sourceCommit": source_commit(), "ingestion": ingestion.model_dump(mode="json"), "providerEnv": env}
    model_path = model_path_from_env()
    if not model_path:
        runtime = GovernedHybridRuntime(chunks=chunks, provider=DisabledEmbeddingProvider("MODEL_ASSET_UNAVAILABLE_SKIP"), fallback_provider="hash")
        candidates, trace = runtime.search("refund broken", tenant_id="tenant-a", mode="hybrid-real")
        result.update({"status": "AGENT_RAG_REAL_DENSE_NOT_VERIFIED", "reason": "RAG_BGE_M3_MODEL_PATH_NOT_CONFIGURED", "fallbackE2E": trace.denseFallbackUsed and trace.effectiveRetrievalMode == "hybrid-hash" and bool(candidates)})
        write_json(PHASE3A_OUT / "real-dense-e2e.json", result)
        return result
    provider = BgeM3EmbeddingProvider(BgeM3ProviderConfig(model_path=Path(model_path), device=env["device"], batch_size=env["batchSize"], max_length=env["maxLength"], normalize=env["normalize"]))
    index_root = PHASE3A_OUT / "e2e-faiss-index"
    if index_root.exists():
        shutil.rmtree(index_root)
    index = FaissVectorIndex(index_root)
    try:
        v1 = index.build(chunks=chunks, provider=provider, tenant_id="tenant-a", index_version="phase3a-e2e-v1", source_commit=source_commit())
        active_v1 = index.activate(v1.indexVersion, provider.metadata(), tenant_id="tenant-a")
        runtime = GovernedHybridRuntime(chunks=chunks, provider=provider, faiss_index=index, fallback_provider="hash", real_dense_required=True)
        dense_hits, dense_trace = runtime.search("refund broken after-sales", tenant_id="tenant-a", mode="real-dense")
        hybrid_hits, hybrid_trace = runtime.search("unsafe smoke fire", tenant_id="tenant-a", mode="hybrid-real")
        cross_hits, _ = runtime.search("tenant b refund private", tenant_id="tenant-a", mode="hybrid-real")
        incompatible_blocked = False
        active_before = index.active_version()
        try:
            bad = dict(provider.metadata())
            bad["dimension"] = int(bad["dimension"]) + 1
            index.activate(active_v1.indexVersion, bad, tenant_id="tenant-a")
        except IndexCompatibilityError:
            incompatible_blocked = index.active_version() == active_before
        v2 = index.build(chunks=chunks, provider=provider, tenant_id="tenant-a", index_version="phase3a-e2e-v2", source_commit=source_commit())
        index.activate(v2.indexVersion, provider.metadata(), tenant_id="tenant-a")
        rollback = index.rollback(provider.metadata(), tenant_id="tenant-a", previous_version=v1.indexVersion)
        result.update(
            {
                "status": "AGENT_RAG_PHASE3A_REAL_DENSE_E2E_PASS",
                "providerMetadata": provider.metadata(),
                "manifest": active_v1.to_dict(),
                "denseRetrieval": bool(dense_hits) and dense_trace.modelFingerprint == active_v1.modelFingerprint,
                "hybridRetrieval": bool(hybrid_hits) and hybrid_trace.effectiveRetrievalMode == "hybrid-real",
                "tenantIsolation": all(hit.tenantId in {"tenant-a", "__public__"} for hit in cross_hits),
                "incompatibleIndexBlocked": incompatible_blocked,
                "rollback": rollback.indexVersion == v1.indexVersion,
                "agentEvidenceBundleFields": {
                    "modelFingerprint": hybrid_trace.modelFingerprint,
                    "indexVersion": hybrid_trace.indexVersion,
                    "denseProvider": hybrid_trace.denseProvider,
                },
            }
        )
        if not all([result["denseRetrieval"], result["hybridRetrieval"], result["tenantIsolation"], result["incompatibleIndexBlocked"], result["rollback"]]):
            result["status"] = "AGENT_RAG_PHASE3A_REAL_DENSE_E2E_FAIL"
    except Exception as exc:
        result.update({"status": "AGENT_RAG_PHASE3A_REAL_DENSE_E2E_FAIL", "reason": str(exc)})
    finally:
        provider.close()
    write_json(PHASE3A_OUT / "real-dense-e2e.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
