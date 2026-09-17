from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
for path in (AI_ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent_rag_phase3a_common import provider_env, write_json
from agent_rag_phase3a2_common import PHASE3A2_OUT
from app.agent_rag.embedding_provider import BgeM3EmbeddingProvider, BgeM3ProviderConfig, HashEmbeddingProvider


def run() -> dict[str, Any]:
    env = provider_env()
    model_path = os.getenv("RAG_BGE_M3_MODEL_PATH", "").strip()
    provider_type = "bge-m3" if model_path else "hash"
    provider = (
        BgeM3EmbeddingProvider(
            BgeM3ProviderConfig(
                model_path=Path(model_path),
                device=env["device"],
                batch_size=4,
                max_length=env["maxLength"],
                normalize=env["normalize"],
            )
        )
        if model_path
        else HashEmbeddingProvider(dimensions=64)
    )
    texts = [
        "商品充电时冒烟并伴随焦糊味，需要升级为产品安全风险。",
        "商品充电时冒烟并伴随焦糊味，需要升级为产品安全风险。",
        "充电的时候出现烟味和发热，可能存在安全隐患。",
        "用户买到坏件，希望按售后政策退货退款。",
        "The parcel tracking has not moved for several days.",
        "直播带货达人佣金结算规则与本知识库无关。",
        "儿童使用充电器时外壳发烫，需要人工复核。",
        "fake promotion and invoice mismatch may indicate counterfeit risk.",
    ]
    try:
        matrix = provider.embed_documents(texts)
        sims = matrix @ matrix.T
        norms = np.linalg.norm(matrix, axis=1)
        duplicate_count = _duplicate_count(matrix, threshold=0.999999)
        near_duplicate_count = _duplicate_count(matrix, threshold=0.98)
        same_text = float(sims[0, 1])
        synonym = float(sims[0, 2])
        unrelated = float(sims[0, 5])
        related = float(sims[0, 6])
        stable = abs(1.0 - same_text) < 1e-4
        sanity_pass = bool(
            same_text > synonym
            and synonym > unrelated
            and related > unrelated
            and stable
            and duplicate_count <= 1
            and np.isfinite(matrix).all()
            and int(np.sum(norms < 1e-8)) == 0
        )
        result = {
            "status": "AGENT_RAG_EMBEDDING_HEALTH_PASS" if sanity_pass else "AGENT_RAG_EMBEDDING_HEALTH_FAIL",
            "providerType": provider_type,
            "modelPathConfigured": bool(model_path),
            "providerMetadata": _sanitize(provider.metadata()),
            "vectorCount": int(matrix.shape[0]),
            "dimension": int(matrix.shape[1]),
            "nanCount": int(np.isnan(matrix).sum()),
            "infCount": int(np.isinf(matrix).sum()),
            "zeroVectorCount": int(np.sum(norms < 1e-8)),
            "duplicateVectorCount": duplicate_count,
            "nearDuplicateVectorCount": near_duplicate_count,
            "norm": _dist(norms.tolist()),
            "pairwiseCosine": _dist(sims[np.triu_indices_from(sims, k=1)].tolist()),
            "sameTextRepeatSimilarity": round(same_text, 6),
            "relatedTextSimilarity": round(related, 6),
            "synonymTextSimilarity": round(synonym, 6),
            "unrelatedTextSimilarity": round(unrelated, 6),
            "crossTenantTextSimilarity": round(float(sims[3, 4]), 6),
            "sanityRules": {
                "sameTextGreaterThanSynonym": same_text > synonym,
                "synonymGreaterThanUnrelated": synonym > unrelated,
                "relatedGreaterThanUnrelated": related > unrelated,
                "repeatStable": stable,
                "noMassiveDuplicateEmbedding": duplicate_count <= 1,
            },
        }
    except Exception as exc:
        result = {
            "status": "AGENT_RAG_EMBEDDING_HEALTH_FAIL",
            "providerType": provider_type,
            "modelPathConfigured": bool(model_path),
            "reason": str(exc)[:240],
        }
    finally:
        provider.close()
    write_json(PHASE3A2_OUT / "embedding-health.json", result)
    return result


def _sanitize(meta: dict[str, Any]) -> dict[str, Any]:
    payload = dict(meta)
    payload.pop("modelPath", None)
    return payload


def _duplicate_count(matrix: np.ndarray, *, threshold: float) -> int:
    sims = matrix @ matrix.T
    count = 0
    for row in range(sims.shape[0]):
        for col in range(row + 1, sims.shape[1]):
            count += int(float(sims[row, col]) >= threshold)
    return count


def _dist(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p95": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0}
    ordered = sorted(float(value) for value in values)
    return {
        "min": round(min(ordered), 6),
        "p25": round(ordered[round((len(ordered) - 1) * 0.25)], 6),
        "p50": round(ordered[round((len(ordered) - 1) * 0.5)], 6),
        "p75": round(ordered[round((len(ordered) - 1) * 0.75)], 6),
        "p95": round(ordered[round((len(ordered) - 1) * 0.95)], 6),
        "max": round(max(ordered), 6),
        "mean": round(float(np.mean(ordered)), 6),
        "std": round(float(np.std(ordered)), 6),
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
