from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from app.agent_rag.contracts import Citation
from app.agent_rag.eligibility import evaluate_evidence_eligibility
from app.agent_rag.knowledge import KnowledgeChunk
from app.rag.dense_retriever import HashDenseRetriever
from app.rag.document_contract import stable_hash
from app.rag.sparse_retriever import BM25Retriever
from app.rag.tenant_acl import normalize_tenant_id


RetrievalMode = Literal["sparse-only", "dense-only", "hybrid"]


@dataclass(frozen=True)
class QueryAnalysis:
    originalQuery: str
    normalizedQuery: str
    rewrittenQueries: list[str]
    language: str
    queryLength: int
    riskIntent: str
    entityHints: list[str]
    timeSensitivity: bool
    preferredSourceTypes: list[str]


@dataclass(frozen=True)
class RetrievalCandidate:
    retrieverType: str
    tenantId: str
    documentId: str
    chunkId: str
    sparseScore: float = 0.0
    denseScore: float = 0.0
    sparseRank: int | None = None
    denseRank: int | None = None
    rawRank: int = 0
    fusionScore: float = 0.0
    fusionRank: int = 0
    row: dict[str, Any] | None = None


@dataclass(frozen=True)
class RerankTrace:
    rerankerType: str
    rerankerVersion: str
    inputCount: int
    outputCount: int
    scores: list[float]
    durationMs: int
    fallbackUsed: bool


class QueryAnalyzer:
    def analyze(self, query: str, *, expansion_enabled: bool = True, expansion_max: int = 3) -> QueryAnalysis:
        normalized = re.sub(r"\s+", " ", query.strip())[:1024]
        lowered = normalized.lower()
        risk_intent = "normal"
        source_types: list[str] = []
        expansions = [normalized]
        if any(term in lowered for term in ["refund", "return", "退货", "退款", "售后"]):
            risk_intent = "after_sales"
            source_types = ["policy", "customer-service", "public-regulation"]
            expansions += ["refund broken after-sales policy", "customer service return handling"]
        elif any(term in lowered for term in ["unsafe", "fire", "smoke", "起火", "安全"]):
            risk_intent = "safety"
            source_types = ["platform-rule", "product-manual", "risk-case"]
            expansions += ["product safety risk escalation", "unsafe product evidence"]
        elif any(term in lowered for term in ["fake", "counterfeit", "虚假"]):
            risk_intent = "fraud"
            source_types = ["platform-rule", "risk-case"]
            expansions += ["fake promotion counterfeit risk", "platform rule fraud"]
        elif any(term in lowered for term in ["delay", "slow", "物流", "延迟"]):
            risk_intent = "logistics"
            source_types = ["faq", "customer-service"]
            expansions += ["logistics delay service policy"]
        unique = []
        for item in expansions:
            if item and item not in unique:
                unique.append(item)
        if not expansion_enabled:
            unique = [normalized]
        return QueryAnalysis(
            originalQuery=query,
            normalizedQuery=normalized,
            rewrittenQueries=unique[: max(1, expansion_max)],
            language="mixed" if re.search(r"[A-Za-z]", normalized) and re.search(r"[\u4e00-\u9fff]", normalized) else ("zh-CN" if re.search(r"[\u4e00-\u9fff]", normalized) else "en"),
            queryLength=len(normalized),
            riskIntent=risk_intent,
            entityHints=re.findall(r"[A-Z]{2,}-?\d+|[\u4e00-\u9fff]{2,}", normalized)[:8],
            timeSensitivity=any(term in lowered for term in ["current", "today", "as of", "当前", "今天"]),
            preferredSourceTypes=source_types,
        )


class RrfHybridRetriever:
    def __init__(self, chunks: list[KnowledgeChunk], *, rrf_k: int = 60, mode: RetrievalMode = "hybrid"):
        self.chunks = chunks
        self.rows = [chunk.as_retriever_row() for chunk in chunks]
        self.rrf_k = rrf_k
        self.mode = mode

    def search(
        self,
        query: str,
        *,
        tenant_id: str,
        as_of_time: str | None = None,
        sparse_top_k: int = 20,
        dense_top_k: int = 20,
        fusion_top_k: int = 8,
    ) -> tuple[list[RetrievalCandidate], dict[str, int]]:
        tenant = normalize_tenant_id(tenant_id)
        rows = [row for row in self.rows if self._visible(row, tenant, as_of_time)]
        sparse_hits = [] if self.mode == "dense-only" else BM25Retriever(rows).search(query, sparse_top_k)
        dense_hits = [] if self.mode == "sparse-only" else HashDenseRetriever(rows, dimensions=64).search(query, dense_top_k)
        by_chunk: dict[str, dict[str, Any]] = {}
        for hit in sparse_hits:
            by_chunk.setdefault(hit.chunk_id, {"sparseRank": None, "denseRank": None, "sparseScore": 0.0, "denseScore": 0.0})
            by_chunk[hit.chunk_id].update({"sparseRank": hit.rank, "sparseScore": hit.score})
        for hit in dense_hits:
            by_chunk.setdefault(hit.chunk_id, {"sparseRank": None, "denseRank": None, "sparseScore": 0.0, "denseScore": 0.0})
            by_chunk[hit.chunk_id].update({"denseRank": hit.rank, "denseScore": hit.score})
        row_by_chunk = {row["chunk_id"]: row for row in rows}
        candidates: list[RetrievalCandidate] = []
        for chunk_id, ranks in by_chunk.items():
            sparse_rank = ranks["sparseRank"]
            dense_rank = ranks["denseRank"]
            score = 0.0
            if sparse_rank:
                score += 1 / (self.rrf_k + sparse_rank)
            if dense_rank:
                score += 1 / (self.rrf_k + dense_rank)
            if self.mode == "hybrid" and (sparse_rank or dense_rank):
                score += 1 / (self.rrf_k + min(rank for rank in [sparse_rank, dense_rank] if rank))
            row = row_by_chunk[chunk_id]
            candidates.append(
                RetrievalCandidate(
                    retrieverType=self.mode,
                    tenantId=str(row["tenant_id"]),
                    documentId=str(row["document_id"]),
                    chunkId=str(chunk_id),
                    sparseScore=float(ranks["sparseScore"]),
                    denseScore=float(ranks["denseScore"]),
                    sparseRank=sparse_rank,
                    denseRank=dense_rank,
                    rawRank=min([rank for rank in [sparse_rank, dense_rank] if rank] or [9999]),
                    fusionScore=round(score, 8),
                    row=row,
                )
            )
        candidates.sort(
            key=lambda item: (
                item.fusionScore,
                -(item.denseRank or 9999),
                -(item.sparseRank or 9999),
            ),
            reverse=True,
        )
        ranked = [
            RetrievalCandidate(**{**candidate.__dict__, "fusionRank": rank})
            for rank, candidate in enumerate(candidates[:fusion_top_k], start=1)
        ]
        return ranked, {"sparseCount": len(sparse_hits), "denseCount": len(dense_hits), "candidateCount": len(candidates)}

    def _visible(self, row: dict[str, Any], tenant: str, as_of_time: str | None) -> bool:
        if row.get("deleted") or row.get("active") is False:
            return False
        if row.get("tenant_id") not in {tenant, "__public__"}:
            return False
        if row.get("tenant_id") == "__public__" and row.get("visibility") != "public":
            return False
        moment = as_of_time or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return evaluate_evidence_eligibility(row, tenant, moment).eligible


class BaseReranker:
    reranker_type = "base"
    reranker_version = "v1"

    def rerank(self, query: str, candidates: list[RetrievalCandidate], top_k: int) -> tuple[list[RetrievalCandidate], RerankTrace]:
        raise NotImplementedError


class DisabledReranker(BaseReranker):
    reranker_type = "disabled"

    def rerank(self, query: str, candidates: list[RetrievalCandidate], top_k: int) -> tuple[list[RetrievalCandidate], RerankTrace]:
        return candidates[:top_k], RerankTrace("disabled", self.reranker_version, len(candidates), min(top_k, len(candidates)), [], 0, False)


class DeterministicReranker(BaseReranker):
    reranker_type = "deterministic"

    def rerank(self, query: str, candidates: list[RetrievalCandidate], top_k: int) -> tuple[list[RetrievalCandidate], RerankTrace]:
        started = time.perf_counter()
        terms = set(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+", query.lower()))
        scored = []
        for candidate in candidates:
            text = str((candidate.row or {}).get("content") or "").lower()
            overlap = sum(1 for term in terms if term in text)
            score = candidate.fusionScore + overlap * 0.01
            scored.append((score, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        output = [item[1] for item in scored[:top_k]]
        return output, RerankTrace("deterministic", "phase2-deterministic-v1", len(candidates), len(output), [round(item[0], 6) for item in scored[:top_k]], round((time.perf_counter() - started) * 1000), False)


class FailingModelReranker(BaseReranker):
    reranker_type = "model"

    def rerank(self, query: str, candidates: list[RetrievalCandidate], top_k: int) -> tuple[list[RetrievalCandidate], RerankTrace]:
        output, trace = DeterministicReranker().rerank(query, candidates, top_k)
        return output, RerankTrace("deterministic", "phase2-fallback-after-model-failure", len(candidates), len(output), trace.scores, trace.durationMs, True)


class EvidenceQualityGate:
    def __init__(self, *, min_score: float = 0.0):
        self.min_score = min_score

    def filter(self, candidates: list[RetrievalCandidate], *, tenant_id: str) -> tuple[list[RetrievalCandidate], list[dict[str, Any]]]:
        tenant = normalize_tenant_id(tenant_id)
        accepted = []
        quality = []
        seen: set[str] = set()
        for candidate in candidates:
            row = candidate.row or {}
            flags = []
            content_hash = str(row.get("content_hash") or "")
            if candidate.tenantId not in {tenant, "__public__"}:
                flags.append("cross-tenant")
            if not content_hash or not row.get("document_id") or not row.get("chunk_id"):
                flags.append("missing-metadata")
            if candidate.fusionScore < self.min_score:
                flags.append("low-score")
            if content_hash in seen:
                flags.append("duplicate")
            if not str(row.get("content") or "").strip():
                flags.append("empty-text")
            if row.get("active") is False:
                flags.append("inactive")
            accepted_flag = not flags
            if accepted_flag:
                seen.add(content_hash)
                accepted.append(candidate)
            quality.append({"chunkId": candidate.chunkId, "accepted": accepted_flag, "flags": flags or ["accepted"]})
        return accepted, quality


def candidates_to_citations(candidates: list[RetrievalCandidate]) -> list[Citation]:
    citations = []
    for rank, candidate in enumerate(candidates, start=1):
        row = candidate.row or {}
        citations.append(
            Citation(
                documentId=candidate.documentId,
                chunkId=candidate.chunkId,
                tenantId=candidate.tenantId,
                sourceType=str(row.get("source_type") or "policy"),
                title=str(row.get("title") or candidate.documentId),
                score=float(candidate.fusionScore),
                rank=rank,
                contentHash=str(row.get("content_hash") or stable_hash(str(row.get("content") or ""))),
                snippet=str(row.get("content") or "")[:180],
            )
        )
    return citations


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
