from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from app.rag.dense_retriever import DenseHit, HashDenseRetriever
from app.rag.embedding_provider import BgeM3EmbeddingProviderConfig, local_bge_m3_provider
from app.rag.versioned_faiss_index import VersionedFaissIndex


EXPECTED_BGE_M3_HASH = "dfb1897399b5033f6cf3a6c0f14395a9de4c5629de470c8b17db52464c768602"


class DenseSearchProvider(Protocol):
    provider_mode: str

    def search(self, query: str, top_k: int = 20, *, tenant_id: str | None = None) -> list[DenseHit]:
        ...

    def status(self) -> dict:
        ...


class DisabledDenseProvider:
    provider_mode = "disabled"

    def __init__(self, reason: str = "DENSE_UNAVAILABLE_SPARSE_DEGRADED"):
        self.reason = reason

    def search(self, query: str, top_k: int = 20, *, tenant_id: str | None = None) -> list[DenseHit]:
        return []

    def status(self) -> dict:
        return {"provider_mode": self.provider_mode, "status": self.reason, "dense_enabled": False}


class HashDenseNegativeControlProvider(HashDenseRetriever):
    provider_mode = "hash_negative_control"

    def status(self) -> dict:
        return {"provider_mode": self.provider_mode, "status": "NEGATIVE_CONTROL_ONLY", "dense_enabled": True}


@dataclass(frozen=True)
class FaissDenseProviderConfig:
    index_root: Path
    model_dir: Path
    device: str = "cpu"
    expected_model_hash: str = EXPECTED_BGE_M3_HASH


class FaissDenseProvider:
    provider_mode = "real_bge_m3_faiss"

    def __init__(self, config: FaissDenseProviderConfig):
        self.config = config
        self.index_store = VersionedFaissIndex(config.index_root)
        self.embedding = local_bge_m3_provider(model_dir=config.model_dir, device=config.device)
        metadata = self.embedding.metadata()
        if metadata["model_hash"] != config.expected_model_hash:
            raise ValueError("BGE_M3_MODEL_HASH_MISMATCH")
        self.model_hash = metadata["model_hash"]

    def search(self, query: str, top_k: int = 20, *, tenant_id: str | None = None) -> list[DenseHit]:
        index, rows, manifest = self.index_store.load_active()
        query_vector = self.embedding.encode_queries([query]).astype("float32")
        scores, ids = index.search(query_vector, max(top_k * 4, top_k))
        hits: list[DenseHit] = []
        rank = 1
        for score, row_id in zip(scores[0], ids[0]):
            if row_id < 0:
                continue
            row = rows[int(row_id)]
            if tenant_id and row.get("tenant_id") != tenant_id:
                continue
            hits.append(
                DenseHit(
                    chunk_id=str(row["chunk_id"]),
                    document_id=str(row["document_id"]),
                    score=round(float(score), 6),
                    rank=rank,
                    embedding_version=manifest.index_version,
                )
            )
            rank += 1
            if len(hits) >= top_k:
                break
        return hits

    def status(self) -> dict:
        return {
            "provider_mode": self.provider_mode,
            "status": "REAL_BGE_M3_FAISS_READY",
            "dense_enabled": True,
            "model_id": "BAAI/bge-m3",
            "model_hash": self.model_hash,
            "index_version": self.index_store.active_version(),
        }

    def close(self) -> None:
        self.embedding.close()


def create_dense_provider(
    *,
    provider_mode: str,
    enterprise_mode: bool = True,
    chunks: list[dict] | None = None,
    index_root: Path | None = None,
    model_dir: Path | None = None,
    device: str = "cpu",
) -> DenseSearchProvider:
    if enterprise_mode and provider_mode == "hash_negative_control":
        raise ValueError("HASH_DENSE_FORBIDDEN_IN_ENTERPRISE_MODE")
    if provider_mode == "disabled":
        return DisabledDenseProvider()
    if provider_mode == "hash_negative_control":
        return HashDenseNegativeControlProvider(chunks or [])
    if provider_mode == "real_bge_m3":
        if not index_root or not model_dir:
            return DisabledDenseProvider("DENSE_UNAVAILABLE_SPARSE_DEGRADED")
        try:
            return FaissDenseProvider(FaissDenseProviderConfig(index_root=index_root, model_dir=model_dir, device=device))
        except Exception:
            return DisabledDenseProvider("DENSE_UNAVAILABLE_SPARSE_DEGRADED")
    raise ValueError("UNKNOWN_DENSE_PROVIDER_MODE")
