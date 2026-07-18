from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from app.rag_v2.dense_encoder import BgeM3Encoder


class EmbeddingProvider(Protocol):
    def encode_documents(self, texts: list[str]) -> np.ndarray:
        ...

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        ...

    def metadata(self) -> dict:
        ...

    def health_check(self) -> dict:
        ...

    def close(self) -> None:
        ...


@dataclass(frozen=True)
class BgeM3EmbeddingProviderConfig:
    model_dir: Path
    device: str = "cpu"
    batch_size: int = 8
    normalize: bool = True
    max_length: int = 512
    expected_model_hash: str | None = None


class BgeM3EmbeddingProvider:
    provider_name = "bge_m3"
    model_id = "BAAI/bge-m3"

    def __init__(self, config: BgeM3EmbeddingProviderConfig):
        self.config = config
        self.encoder = BgeM3Encoder(
            config.model_dir,
            device=config.device,
            batch_size=config.batch_size,
            normalize=config.normalize,
            max_length=config.max_length,
        )
        self._model_hash: str | None = None

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return self._validate(self.encoder.encode_documents(texts))

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return self._validate(self.encoder.encode_queries(texts))

    def metadata(self) -> dict:
        model_hash = self.model_hash()
        if self.config.expected_model_hash and not model_hash.startswith(self.config.expected_model_hash.lower()):
            raise ValueError("EMBEDDING_MODEL_HASH_MISMATCH")
        return {
            "provider": self.provider_name,
            "model_id": self.model_id,
            "model_hash": model_hash,
            "dimension": self.encoder.dimension,
            "device": self.encoder.device or self.config.device,
            "normalized": self.config.normalize,
            "model_path_label": "<repo-external>/models/bge-m3",
        }

    def health_check(self) -> dict:
        return {
            "available": self.encoder.available,
            "provider": self.provider_name,
            "model_id": self.model_id,
            "model_path_label": "<repo-external>/models/bge-m3",
            "model_hash_present": bool(self.model_hash()) if self.encoder.available else False,
        }

    def close(self) -> None:
        self.encoder.unload()

    def model_hash(self) -> str:
        if self._model_hash:
            return self._model_hash
        weight = self.config.model_dir / "model.safetensors"
        if not weight.exists():
            raise RuntimeError("EMBEDDING_MODEL_WEIGHT_NOT_FOUND")
        digest = hashlib.sha256()
        with weight.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        self._model_hash = digest.hexdigest()
        return self._model_hash

    @staticmethod
    def _validate(vectors: np.ndarray) -> np.ndarray:
        matrix = np.asarray(vectors, dtype="float32")
        if matrix.ndim != 2:
            raise ValueError("EMBEDDING_VECTOR_RANK_INVALID")
        if not np.isfinite(matrix).all():
            raise ValueError("EMBEDDING_VECTOR_NAN_OR_INF")
        norms = np.linalg.norm(matrix, axis=1)
        if np.any(norms == 0):
            raise ValueError("EMBEDDING_ZERO_VECTOR")
        normalized = matrix / norms.reshape(-1, 1)
        return normalized.astype("float32")


def local_bge_m3_provider(model_dir: Path | None = None, device: str = "cpu") -> BgeM3EmbeddingProvider:
    root = Path(__file__).resolve().parents[3]
    return BgeM3EmbeddingProvider(BgeM3EmbeddingProviderConfig(model_dir=model_dir or root.parent / "models" / "bge-m3", device=device))
