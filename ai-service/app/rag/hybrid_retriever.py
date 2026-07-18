from __future__ import annotations

from dataclasses import dataclass

from app.rag.dense_provider_factory import DenseSearchProvider, DisabledDenseProvider
from app.rag.sparse_retriever import BM25Retriever


@dataclass(frozen=True)
class HybridHit:
    document_id: str
    chunk_id: str
    version: str
    sparse_rank: int | None
    dense_rank: int | None
    fused_rank: int
    fused_score: float
    source: str
    trust_level: str


class HybridRetriever:
    def __init__(self, chunks: list[dict], sparse: BM25Retriever | None = None, dense: DenseSearchProvider | None = None, rrf_k: int = 60):
        self.chunks = {row["chunk_id"]: row for row in chunks}
        self.sparse = sparse or BM25Retriever(chunks)
        self.dense = dense or DisabledDenseProvider()
        self.rrf_k = rrf_k
        self.provider_mode = getattr(self.dense, "provider_mode", "disabled")

    def search(
        self,
        query: str,
        *,
        sparse_top_k: int = 20,
        dense_top_k: int = 20,
        fused_top_k: int = 12,
        tenant_id: str | None = None,
    ) -> list[HybridHit]:
        sparse_hits = self.sparse.search(query, sparse_top_k, tenant_id=tenant_id)
        dense_hits = self.dense.search(query, dense_top_k, tenant_id=tenant_id)
        ranks: dict[str, dict[str, int | None]] = {}
        for hit in sparse_hits:
            ranks.setdefault(hit.chunk_id, {"sparse": None, "dense": None})["sparse"] = hit.rank
        for hit in dense_hits:
            ranks.setdefault(hit.chunk_id, {"sparse": None, "dense": None})["dense"] = hit.rank
        scored = []
        for chunk_id, row in ranks.items():
            sparse_rank = row.get("sparse")
            dense_rank = row.get("dense")
            score = 0.0
            if sparse_rank:
                score += 1 / (self.rrf_k + sparse_rank)
            if dense_rank:
                score += 1 / (self.rrf_k + dense_rank)
            scored.append((score, chunk_id, sparse_rank, dense_rank))
        scored.sort(key=lambda item: item[0], reverse=True)
        output = []
        for fused_rank, (score, chunk_id, sparse_rank, dense_rank) in enumerate(scored[:fused_top_k], start=1):
            chunk = self.chunks[chunk_id]
            source = "hybrid" if sparse_rank and dense_rank else ("sparse" if sparse_rank else "dense")
            output.append(
                HybridHit(
                    document_id=str(chunk["document_id"]),
                    chunk_id=str(chunk_id),
                    version=str(chunk.get("document_version") or ""),
                    sparse_rank=sparse_rank,
                    dense_rank=dense_rank,
                    fused_rank=fused_rank,
                    fused_score=round(score, 8),
                    source=source,
                    trust_level=str(chunk.get("trust_level") or "internal_unverified"),
                )
            )
        return output

    def status(self) -> dict:
        dense_status = self.dense.status() if hasattr(self.dense, "status") else {"provider_mode": self.provider_mode}
        return {
            "provider_mode": self.provider_mode,
            "dense": dense_status,
            "hybrid_status": "HYBRID_RRF_WITH_REAL_DENSE" if dense_status.get("dense_enabled") else "DENSE_UNAVAILABLE_SPARSE_DEGRADED",
        }
