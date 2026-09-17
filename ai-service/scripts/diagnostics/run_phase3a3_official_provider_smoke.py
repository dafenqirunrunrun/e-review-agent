from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
for path in (AI_ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent_rag_phase3a3_common import make_provider, write_phase3a3_json


def run() -> dict:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("RAG_DENSE_PROVIDER", "bge-m3")
    os.environ.setdefault("RAG_BGE_M3_PROVIDER_IMPL", "flagembedding")
    os.environ.setdefault("RAG_BGE_M3_DEVICE", "cuda")
    os.environ.setdefault("RAG_BGE_M3_USE_FP16", "true")
    os.environ.setdefault("RAG_BGE_M3_BATCH_SIZE", "1")
    os.environ.setdefault("RAG_BGE_M3_MAX_LENGTH", "512")
    os.environ.setdefault("RAG_BGE_M3_NORMALIZE", "true")

    started = time.perf_counter_ns()
    provider = make_provider("flagembedding")
    payload: dict = {
        "schemaVersion": "1.0.0",
        "providerImpl": "flagembedding",
        "providerConformance": "official-library",
        "offlineMode": {
            "HF_HUB_OFFLINE": os.getenv("HF_HUB_OFFLINE"),
            "TRANSFORMERS_OFFLINE": os.getenv("TRANSFORMERS_OFFLINE"),
        },
        "modelPathConfigured": bool(os.getenv("RAG_BGE_M3_MODEL_PATH", "").strip()),
    }
    try:
        matrix = provider.embed_documents(
            [
                "售后投诉：商品外包装完好，但内部屏幕碎裂，图片与实物损坏情况一致，需要人工处理。",
                "正向评价：发货速度很快，商品与详情页一致，包装完整。",
            ]
        )
        first = provider.embed_query("售后投诉商品破损需要人工处理")
        repeated = provider.embed_query("售后投诉商品破损需要人工处理")
        metadata = provider.metadata()
        norms = [float(math.sqrt(float((row * row).sum()))) for row in matrix]
        payload.update(
            {
                "status": "PASS",
                "batchCount": int(matrix.shape[0]),
                "dimension": int(matrix.shape[1]),
                "queryDimension": int(first.shape[1]),
                "hasNan": bool(~(matrix == matrix).all()),
                "hasInf": bool(abs(matrix).max() == float("inf")),
                "norms": norms,
                "sameTextStable": bool(abs(float((first[0] - repeated[0]).max())) < 1e-5),
                "metadata": metadata,
                "elapsedMs": round((time.perf_counter_ns() - started) / 1_000_000, 3),
            }
        )
        if matrix.shape != (2, 1024) or first.shape[1] != 1024:
            payload["status"] = "BLOCKED"
            payload["reason"] = "FLAGEMBEDDING_WRONG_DIMENSION"
        elif payload["hasNan"] or payload["hasInf"]:
            payload["status"] = "BLOCKED"
            payload["reason"] = "FLAGEMBEDDING_VECTOR_INVALID"
    except Exception as exc:
        payload.update({"status": "BLOCKED", "reason": str(exc)[:400], "elapsedMs": round((time.perf_counter_ns() - started) / 1_000_000, 3)})
    finally:
        provider.close()

    write_phase3a3_json("official-provider-smoke.json", payload)
    return payload


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "PASS":
        print("AGENT_RAG_OFFICIAL_PROVIDER_RUNTIME_PASS")
    raise SystemExit(0 if result["status"] == "PASS" else 2)
