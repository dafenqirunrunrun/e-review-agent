from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
for path in (AI_ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent_rag_phase3a2_common import evaluate_cases, phase3a2_cases, split_cases
from agent_rag_phase3a_common import phase3a_all_tenant_chunks, provider_env, source_commit, write_json
from app.agent_rag.embedding_provider import BaseEmbeddingProvider
from app.agent_rag.faiss_index import FaissVectorIndex
from app.agent_rag.phase3a_retrieval import make_bge_m3_provider
from app.rag.document_contract import stable_hash


PHASE3A3_OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-phase3a3"
PROVIDER_IMPLS = ("legacy-cls", "flagembedding", "sentence-transformers")


def provider_config(provider_impl: str) -> dict[str, Any]:
    env = provider_env()
    return {
        "providerImpl": provider_impl,
        "modelPathConfigured": bool(os.getenv("RAG_BGE_M3_MODEL_PATH", "").strip()),
        "device": os.getenv("RAG_BGE_M3_DEVICE", env["device"]),
        "batchSize": int(os.getenv("RAG_BGE_M3_BATCH_SIZE", str(env["batchSize"]))),
        "maxLength": int(os.getenv("RAG_BGE_M3_MAX_LENGTH", str(env["maxLength"]))),
        "normalize": os.getenv("RAG_BGE_M3_NORMALIZE", "true").lower() == "true",
        "useFp16": os.getenv("RAG_BGE_M3_USE_FP16", "false").lower() == "true",
    }


def make_provider(provider_impl: str) -> BaseEmbeddingProvider:
    cfg = provider_config(provider_impl)
    return make_bge_m3_provider(
        provider_impl=provider_impl,
        model_path=os.getenv("RAG_BGE_M3_MODEL_PATH", "").strip() or "__missing__",
        device=cfg["device"],
        batch_size=cfg["batchSize"],
        max_length=cfg["maxLength"],
        normalize=cfg["normalize"],
        load_on_startup=False,
        use_fp16=cfg["useFp16"],
    )


def provider_status(provider_impl: str) -> dict[str, Any]:
    provider = make_provider(provider_impl)
    try:
        provider.embed_query("provider status probe")
        return {"status": "READY", "metadata": sanitize_metadata(provider.metadata())}
    except Exception as exc:
        return {"status": "BLOCKED", "reason": str(exc)[:240], "metadata": sanitize_metadata(provider.health())}
    finally:
        provider.close()


def build_provider_index(provider: BaseEmbeddingProvider, provider_impl: str, chunks) -> tuple[FaissVectorIndex, dict[str, Any]]:
    index = FaissVectorIndex(PHASE3A3_OUT / f"faiss-{provider_impl}")
    if (PHASE3A3_OUT / f"faiss-{provider_impl}").exists():
        import shutil

        shutil.rmtree(PHASE3A3_OUT / f"faiss-{provider_impl}")
        index = FaissVectorIndex(PHASE3A3_OUT / f"faiss-{provider_impl}")
    manifest = index.build(chunks=chunks, provider=provider, tenant_id="tenant-a", index_version=f"phase3a3-{provider_impl}-v1", source_commit=source_commit())
    active = index.activate(manifest.indexVersion, provider.metadata(), tenant_id="tenant-a")
    return index, active.to_dict()


def benchmark_payload() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Any], dict[str, Any]]:
    ingestion, chunks = phase3a_all_tenant_chunks()
    cases = phase3a2_cases(chunks)
    split = split_cases(cases)
    return split["calibration"], split["evaluation"], chunks, ingestion


def metric_summary_for_provider(provider_impl: str) -> dict[str, Any]:
    _, evaluation, chunks, ingestion = benchmark_payload()
    provider = make_provider(provider_impl)
    started = time.perf_counter_ns()
    try:
        index, manifest = build_provider_index(provider, provider_impl, chunks)
        summary = evaluate_cases(chunks, provider, index, evaluation, sparse_weight=1.0, dense_weight=0.5)
        elapsed_ms = round((time.perf_counter_ns() - started) / 1_000_000, 3)
        return {
            "status": "PASS",
            "providerImpl": provider_impl,
            "providerMetadata": sanitize_metadata(provider.metadata()),
            "manifest": manifest,
            "evaluation": {key: value for key, value in summary.items() if key != "rows"},
            "elapsedMs": elapsed_ms,
            "ingestion": ingestion,
        }
    except Exception as exc:
        return {"status": "BLOCKED", "providerImpl": provider_impl, "reason": str(exc)[:240]}
    finally:
        provider.close()


def sanitize_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    payload = dict(meta)
    payload.pop("modelPath", None)
    return payload


def write_phase3a3_json(name: str, payload: dict[str, Any]) -> Path:
    path = PHASE3A3_OUT / name
    write_json(path, payload)
    return path


def hash_payload(payload: dict[str, Any]) -> str:
    return stable_hash(payload)


def vector_sanity(provider: BaseEmbeddingProvider, rows: list[dict[str, Any]]) -> dict[str, Any]:
    positive_scores = []
    hard_scores = []
    easy_scores = []
    hard_correct = 0
    easy_correct = 0
    for row in rows:
        query = provider.embed_query(row["query"])[0]
        docs = provider.embed_documents([row["positive"], row["hardNegative"], row["easyNegative"]])
        sims = docs @ query
        positive_scores.append(float(sims[0]))
        hard_scores.append(float(sims[1]))
        easy_scores.append(float(sims[2]))
        hard_correct += int(sims[0] > sims[1])
        easy_correct += int(sims[0] > sims[2])
    count = len(rows)
    return {
        "caseCount": count,
        "pairwiseOrderingAccuracy": round((hard_correct + easy_correct) / max(1, count * 2), 4),
        "hardNegativeOrderingAccuracy": round(hard_correct / max(1, count), 4),
        "easyNegativeOrderingAccuracy": round(easy_correct / max(1, count), 4),
        "meanPositiveSimilarity": round(float(np.mean(positive_scores)), 6),
        "meanHardNegativeSimilarity": round(float(np.mean(hard_scores)), 6),
        "meanEasyNegativeSimilarity": round(float(np.mean(easy_scores)), 6),
        "meanPositiveHardMargin": round(float(np.mean(np.asarray(positive_scores) - np.asarray(hard_scores))), 6),
        "meanPositiveEasyMargin": round(float(np.mean(np.asarray(positive_scores) - np.asarray(easy_scores))), 6),
    }
