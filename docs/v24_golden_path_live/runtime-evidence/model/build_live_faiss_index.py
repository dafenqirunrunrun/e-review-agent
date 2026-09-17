from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.agent_rag.faiss_index import FaissVectorIndex
from app.agent_rag.phase3a_retrieval import make_embedding_provider
from app.agent_rag.runtime import _knowledge_chunks_from_rows


ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "ai-service" / "tests" / "fixtures" / "agent_rag" / "phase1_cases.json"
INDEX_ROOT = Path(__file__).resolve().parent / "live-faiss-index"
SUMMARY = Path(__file__).resolve().parent / "live_faiss_index_build.json"


def source_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def load_runtime_chunks() -> list[dict]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = list(payload["chunks"])
    local_rows = []
    for row in rows:
        if row.get("tenant_id") == "tenant-a":
            clone = dict(row)
            clone["tenant_id"] = "__local__"
            clone["chunk_id"] = f"local-{row['chunk_id']}"
            clone["document_id"] = f"local-{row['document_id']}"
            local_rows.append(clone)
    return rows + local_rows


def main() -> None:
    model_path = Path(r"D:\EReviewAgent\models\bge-m3")
    os.environ.setdefault("RAG_BGE_M3_PROVIDER_IMPL", "flagembedding")
    provider = make_embedding_provider(
        "bge-m3",
        model_path=str(model_path),
        device="cuda",
        batch_size=2,
        max_length=384,
        normalize=True,
        load_on_startup=False,
    )
    rows = load_runtime_chunks()
    chunks = _knowledge_chunks_from_rows(rows)
    version = "v24-golden-live-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    index = FaissVectorIndex(INDEX_ROOT)
    manifest = index.build(
        chunks=chunks,
        provider=provider,
        tenant_id="__local__",
        index_version=version,
        source_commit=source_commit(),
    )
    activated = index.activate(version, provider.metadata(), tenant_id="__local__")
    summary = {
        "indexRoot": str(INDEX_ROOT),
        "fixture": str(FIXTURE),
        "sourceCommit": source_commit(),
        "inputRows": len(rows),
        "knowledgeChunks": len(chunks),
        "activeVersion": index.active_version(),
        "providerMetadata": provider.metadata(),
        "manifest": activated.to_dict(),
        "buildStatus": "PASS",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
