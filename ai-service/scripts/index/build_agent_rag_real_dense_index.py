from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))
SCRIPTS = AI_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from agent_rag_phase3a_common import phase3a_chunks, provider_env, source_commit, write_json
from app.agent_rag.embedding_provider import BgeM3EmbeddingProvider, BgeM3ProviderConfig
from app.agent_rag.faiss_index import FaissVectorIndex


def build(*, tenant: str, output_root: Path, index_version: str, model_path: str | None = None) -> dict:
    env = provider_env()
    configured_model_path = model_path or __import__("os").getenv("RAG_BGE_M3_MODEL_PATH", "")
    if not configured_model_path:
        result = {"status": "AGENT_RAG_REAL_DENSE_NOT_VERIFIED", "reason": "RAG_BGE_M3_MODEL_PATH_NOT_CONFIGURED", "providerEnv": env}
        write_json(output_root / "build-result.json", result)
        return result
    ingestion, chunks = phase3a_chunks(tenant)
    provider = BgeM3EmbeddingProvider(
        BgeM3ProviderConfig(
            model_path=Path(configured_model_path),
            device=env["device"],
            batch_size=env["batchSize"],
            max_length=env["maxLength"],
            normalize=env["normalize"],
            load_on_startup=False,
        )
    )
    index = FaissVectorIndex(output_root)
    try:
        manifest = index.build(chunks=chunks, provider=provider, tenant_id=tenant, index_version=index_version, source_commit=source_commit())
        activated = index.activate(index_version, provider.metadata(), tenant_id=tenant)
        hits, active_manifest = index.search(provider.embed_query("refund broken after-sales"), provider.metadata(), tenant_id=tenant, top_k=3)
        result = {
            "status": "AGENT_RAG_REAL_DENSE_INDEX_BUILD_PASS",
            "ingestion": ingestion.model_dump(mode="json"),
            "manifest": activated.to_dict(),
            "smokeHitCount": len(hits),
            "activeIndexVersion": active_manifest.indexVersion,
            "providerMetadata": provider.metadata(),
        }
    except Exception as exc:
        result = {"status": "AGENT_RAG_REAL_DENSE_INDEX_BUILD_FAIL", "reason": str(exc), "ingestion": ingestion.model_dump(mode="json")}
    finally:
        provider.close()
    write_json(output_root / "build-result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="tenant-a")
    parser.add_argument("--output-root", default=str(ROOT / "artifacts" / "agent-rag" / "v2.0-phase3a" / "faiss-index"))
    parser.add_argument("--index-version", default="phase3a-real-dense-v1")
    parser.add_argument("--model-path", default="")
    args = parser.parse_args()
    result = build(tenant=args.tenant, output_root=Path(args.output_root), index_version=args.index_version, model_path=args.model_path or None)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
