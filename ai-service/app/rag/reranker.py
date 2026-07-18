from __future__ import annotations

from dataclasses import dataclass

from app.rag.hybrid_retriever import HybridHit


@dataclass(frozen=True)
class RerankResult:
    status: str
    hits: list[HybridHit]


class LocalRerankerProvider:
    def __init__(self, available: bool = False):
        self.available = available

    def rerank(self, query: str, hits: list[HybridHit]) -> RerankResult:
        if not self.available:
            return RerankResult(status="RERANKER_UNAVAILABLE", hits=hits)
        terms = {term.lower() for term in query.split() if term.strip()}
        ranked = sorted(hits, key=lambda hit: (hit.trust_level == "internal_verified", hit.fused_score, hit.chunk_id in terms), reverse=True)
        return RerankResult(status="PASS", hits=ranked)
