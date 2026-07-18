from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from app.rag.sparse_retriever import tokenize


@dataclass(frozen=True)
class DenseHit:
    chunk_id: str
    document_id: str
    score: float
    rank: int
    embedding_version: str


class HashDenseRetriever:
    """Demo-only dense baseline.

    Enterprise code must use BgeM3EmbeddingProvider plus VersionedFaissIndex.
    This class remains only for tests and negative-control comparisons.
    """
    def __init__(self, chunks: list[dict], embedding_version: str = "hash-v1", dimensions: int = 64):
        self.embedding_version = embedding_version
        self.dimensions = dimensions
        self.chunks = [row for row in chunks if row.get("active", True) and not row.get("deleted", False)]
        self.vectors = {row["chunk_id"]: self._embed(str(row.get("content") or "")) for row in self.chunks}

    def search(self, query: str, top_k: int = 20, *, tenant_id: str | None = None) -> list[DenseHit]:
        query_vector = self._embed(query)
        scored = []
        for row in self.chunks:
            if tenant_id and row.get("tenant_id") != tenant_id:
                continue
            score = self._dot(query_vector, self.vectors[row["chunk_id"]])
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            DenseHit(
                chunk_id=str(row["chunk_id"]),
                document_id=str(row["document_id"]),
                score=round(score, 6),
                rank=rank,
                embedding_version=self.embedding_version,
            )
            for rank, (score, row) in enumerate(scored[:top_k], start=1)
        ]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = digest[0] % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    @staticmethod
    def _dot(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right))
