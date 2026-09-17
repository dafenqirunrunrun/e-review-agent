from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from app.agent_rag.embedding_provider import BaseEmbeddingProvider, BgeM3ProviderConfig, BgeM3EmbeddingProvider, DisabledEmbeddingProvider, HashEmbeddingProvider, OfficialBgeM3FlagProvider, SentenceTransformerBgeM3Provider
from app.agent_rag.faiss_index import FaissVectorIndex, IndexCompatibilityError
from app.agent_rag.eligibility import filter_eligible_candidates, utc_now
from app.agent_rag.knowledge import KnowledgeChunk
from app.agent_rag.phase2_retrieval import RetrievalCandidate, RrfHybridRetriever
from app.agent_rag.reranker import GovernedReranker, load_reranker_config
from app.rag.sparse_retriever import BM25Retriever
from app.rag.tenant_acl import normalize_tenant_id


RuntimeRetrievalMode = Literal["fixture-hash", "real-dense", "hybrid-real", "sparse-only"]


@dataclass(frozen=True)
class DenseRuntimeTrace:
    requestedRetrievalMode: str
    effectiveRetrievalMode: str
    denseProvider: str
    denseFallbackUsed: bool
    denseFallbackReason: str
    embeddingDurationMs: int = 0
    faissSearchDurationMs: int = 0
    embeddingDurationNs: int = 0
    faissSearchDurationNs: int = 0
    indexVersion: str = ""
    modelFingerprint: str = ""
    embeddingDimension: int = 0
    faissIndexType: str = ""
    faissMetric: str = ""


class BgeM3FaissDenseRetriever:
    def __init__(self, *, provider: BaseEmbeddingProvider, index: FaissVectorIndex):
        self.provider = provider
        self.index = index
        self.last_trace = DenseRuntimeTrace(
            requestedRetrievalMode="real-dense",
            effectiveRetrievalMode="real-dense",
            denseProvider="",
            denseFallbackUsed=False,
            denseFallbackReason="",
        )

    def search(self, query: str, *, tenant_id: str, top_k: int = 20) -> list[RetrievalCandidate]:
        started = time.perf_counter_ns()
        vector = self.provider.embed_query(query)
        embedding_ns = time.perf_counter_ns() - started
        embedding_ms = round(embedding_ns / 1_000_000, 3)
        metadata = self.provider.metadata()
        rows, manifest = self.index.search(vector, metadata, tenant_id=tenant_id, top_k=top_k)
        candidates: list[RetrievalCandidate] = []
        for row in rows:
            candidates.append(
                RetrievalCandidate(
                    retrieverType="real-dense",
                    tenantId=str(row["tenantId"]),
                    documentId=str(row["documentId"]),
                    chunkId=str(row["chunkId"]),
                    denseScore=float(row["denseScore"]),
                    denseRank=int(row["denseRank"]),
                    rawRank=int(row["denseRank"]),
                    fusionScore=float(row["denseScore"]),
                    fusionRank=int(row["denseRank"]),
                    row=_row_to_retriever(row),
                )
            )
        self.last_trace = DenseRuntimeTrace(
            requestedRetrievalMode="real-dense",
            effectiveRetrievalMode="real-dense",
            denseProvider=str(metadata["providerType"]),
            denseFallbackUsed=False,
            denseFallbackReason="",
            embeddingDurationMs=embedding_ms,
            faissSearchDurationMs=self.index.last_search_ms,
            embeddingDurationNs=embedding_ns,
            faissSearchDurationNs=self.index.last_search_ns,
            indexVersion=manifest.indexVersion,
            modelFingerprint=manifest.modelFingerprint,
            embeddingDimension=manifest.embeddingDimension,
            faissIndexType=manifest.faissIndexType,
            faissMetric=manifest.faissMetric,
        )
        return candidates


class GovernedHybridRuntime:
    def __init__(
        self,
        *,
        chunks: list[KnowledgeChunk],
        provider: BaseEmbeddingProvider | None = None,
        faiss_index: FaissVectorIndex | None = None,
        fallback_provider: str = "hash",
        real_dense_required: bool = False,
        rrf_k: int = 60,
        sparse_weight: float = 1.0,
        dense_weight: float = 1.0,
    ):
        self.chunks = chunks
        self.provider = provider or DisabledEmbeddingProvider("DENSE_PROVIDER_NOT_CONFIGURED")
        self.faiss_index = faiss_index
        self.fallback_provider = fallback_provider
        self.real_dense_required = real_dense_required
        self.rrf_k = rrf_k
        self.sparse_weight = sparse_weight
        self.dense_weight = dense_weight
        self.last_trace = DenseRuntimeTrace(
            requestedRetrievalMode="sparse-only",
            effectiveRetrievalMode="sparse-only",
            denseProvider="disabled",
            denseFallbackUsed=False,
            denseFallbackReason="",
        )

    def search(
        self,
        query: str,
        *,
        tenant_id: str,
        mode: RuntimeRetrievalMode = "hybrid-real",
        sparse_top_k: int = 20,
        dense_top_k: int = 20,
        fusion_top_k: int = 8,
        rerank_top_k: int | None = None,
        evaluation_time_utc: str | None = None,
    ) -> tuple[list[RetrievalCandidate], DenseRuntimeTrace]:
        evaluation_time = evaluation_time_utc or utc_now()
        if mode == "fixture-hash":
            candidates, _ = RrfHybridRetriever(self.chunks, mode="hybrid", rrf_k=self.rrf_k).search(query, tenant_id=tenant_id, as_of_time=evaluation_time, sparse_top_k=sparse_top_k, dense_top_k=dense_top_k, fusion_top_k=fusion_top_k)
            self.last_trace = DenseRuntimeTrace(
                requestedRetrievalMode=mode,
                effectiveRetrievalMode="fixture-hash",
                denseProvider="hash",
                denseFallbackUsed=False,
                denseFallbackReason="",
            )
            return self._rerank(query, candidates, rerank_top_k, tenant_id=tenant_id, evaluation_time_utc=evaluation_time), self.last_trace
        if mode == "sparse-only":
            candidates = self._sparse(query, tenant_id=tenant_id, top_k=fusion_top_k)
            self.last_trace = DenseRuntimeTrace(
                requestedRetrievalMode=mode,
                effectiveRetrievalMode="sparse-only",
                denseProvider="disabled",
                denseFallbackUsed=False,
                denseFallbackReason="",
            )
            candidates, _ = filter_eligible_candidates(candidates, tenant_id=tenant_id, evaluation_time_utc=evaluation_time)
            return self._rerank(query, candidates, rerank_top_k, tenant_id=tenant_id, evaluation_time_utc=evaluation_time), self.last_trace
        try:
            if not self.faiss_index:
                raise RuntimeError("FAISS_INDEX_NOT_CONFIGURED")
            dense = BgeM3FaissDenseRetriever(provider=self.provider, index=self.faiss_index)
            dense_candidates = dense.search(query, tenant_id=tenant_id, top_k=dense_top_k)
            dense_candidates, _ = filter_eligible_candidates(dense_candidates, tenant_id=tenant_id, evaluation_time_utc=evaluation_time)
            if mode == "real-dense":
                trace = dense.last_trace
                self.last_trace = DenseRuntimeTrace(
                    requestedRetrievalMode=mode,
                    effectiveRetrievalMode="real-dense",
                    denseProvider=trace.denseProvider,
                    denseFallbackUsed=False,
                    denseFallbackReason="",
                    embeddingDurationMs=trace.embeddingDurationMs,
                    faissSearchDurationMs=trace.faissSearchDurationMs,
                    embeddingDurationNs=trace.embeddingDurationNs,
                    faissSearchDurationNs=trace.faissSearchDurationNs,
                    indexVersion=trace.indexVersion,
                    modelFingerprint=trace.modelFingerprint,
                    embeddingDimension=trace.embeddingDimension,
                    faissIndexType=trace.faissIndexType,
                    faissMetric=trace.faissMetric,
                )
                return self._rerank(query, dense_candidates[:fusion_top_k], rerank_top_k, tenant_id=tenant_id, evaluation_time_utc=evaluation_time), self.last_trace
            sparse_candidates = self._sparse(query, tenant_id=tenant_id, top_k=sparse_top_k)
            sparse_candidates, _ = filter_eligible_candidates(sparse_candidates, tenant_id=tenant_id, evaluation_time_utc=evaluation_time)
            fused = self._fuse(sparse_candidates, dense_candidates, fusion_top_k=fusion_top_k)
            trace = dense.last_trace
            self.last_trace = DenseRuntimeTrace(
                requestedRetrievalMode=mode,
                effectiveRetrievalMode="hybrid-real",
                denseProvider=trace.denseProvider,
                denseFallbackUsed=False,
                denseFallbackReason="",
                embeddingDurationMs=trace.embeddingDurationMs,
                faissSearchDurationMs=trace.faissSearchDurationMs,
                embeddingDurationNs=trace.embeddingDurationNs,
                faissSearchDurationNs=trace.faissSearchDurationNs,
                indexVersion=trace.indexVersion,
                modelFingerprint=trace.modelFingerprint,
                embeddingDimension=trace.embeddingDimension,
                faissIndexType=trace.faissIndexType,
                faissMetric=trace.faissMetric,
            )
            return self._rerank(query, fused, rerank_top_k, tenant_id=tenant_id, evaluation_time_utc=evaluation_time), self.last_trace
        except Exception as exc:
            reason = exc.code if isinstance(exc, IndexCompatibilityError) else str(exc).splitlines()[0][:120]
            if self.real_dense_required:
                raise RuntimeError(f"REAL_DENSE_REQUIRED_UNAVAILABLE:{reason}") from exc
            if self.fallback_provider == "hash":
                candidates, _ = RrfHybridRetriever(self.chunks, mode="hybrid", rrf_k=self.rrf_k).search(query, tenant_id=tenant_id, as_of_time=evaluation_time, sparse_top_k=sparse_top_k, dense_top_k=dense_top_k, fusion_top_k=fusion_top_k)
                self.last_trace = DenseRuntimeTrace(
                    requestedRetrievalMode=mode,
                    effectiveRetrievalMode="hybrid-hash",
                    denseProvider="hash",
                    denseFallbackUsed=True,
                    denseFallbackReason=reason,
                )
                return self._rerank(query, candidates, rerank_top_k, tenant_id=tenant_id, evaluation_time_utc=evaluation_time), self.last_trace
            candidates = self._sparse(query, tenant_id=tenant_id, top_k=fusion_top_k)
            candidates, _ = filter_eligible_candidates(candidates, tenant_id=tenant_id, evaluation_time_utc=evaluation_time)
            self.last_trace = DenseRuntimeTrace(
                requestedRetrievalMode=mode,
                effectiveRetrievalMode="sparse-only",
                denseProvider="disabled",
                denseFallbackUsed=True,
                denseFallbackReason=reason,
            )
            return self._rerank(query, candidates, rerank_top_k, tenant_id=tenant_id, evaluation_time_utc=evaluation_time), self.last_trace

    def health(self) -> dict[str, Any]:
        provider_meta = self.provider.metadata() if not isinstance(self.provider, DisabledEmbeddingProvider) else self.provider.metadata()
        active = self.faiss_index.active_version() if self.faiss_index else ""
        return {
            "status": "ready" if provider_meta.get("loaded") and active else "degraded",
            "requestedProvider": provider_meta.get("providerType", "disabled"),
            "effectiveProvider": provider_meta.get("providerType", "disabled"),
            "modelLoaded": bool(provider_meta.get("loaded")),
            "modelFingerprint": provider_meta.get("modelFingerprint", ""),
            "device": provider_meta.get("device", ""),
            "embeddingDimension": provider_meta.get("dimension", 0),
            "activeIndexVersion": active or "",
            "indexLoaded": bool(active),
            "fallbackUsed": self.last_trace.denseFallbackUsed,
        }

    def _sparse(self, query: str, *, tenant_id: str, top_k: int) -> list[RetrievalCandidate]:
        tenant = normalize_tenant_id(tenant_id)
        rows = [chunk.as_retriever_row() for chunk in self.chunks if chunk.tenantId in {tenant, "__public__"}]
        hits = BM25Retriever(rows).search(query, top_k)
        row_by_chunk = {row["chunk_id"]: row for row in rows}
        return [
            RetrievalCandidate(
                retrieverType="sparse-only",
                tenantId=str(row_by_chunk[hit.chunk_id]["tenant_id"]),
                documentId=hit.document_id,
                chunkId=hit.chunk_id,
                sparseScore=float(hit.score),
                sparseRank=hit.rank,
                rawRank=hit.rank,
                fusionScore=float(hit.score),
                fusionRank=hit.rank,
                row=row_by_chunk[hit.chunk_id],
            )
            for hit in hits
        ]

    def _fuse(self, sparse: list[RetrievalCandidate], dense: list[RetrievalCandidate], *, fusion_top_k: int) -> list[RetrievalCandidate]:
        by_chunk: dict[str, dict[str, Any]] = {}
        for item in sparse:
            by_chunk.setdefault(item.chunkId, {"candidate": item, "sparseRank": None, "denseRank": None, "sparseScore": 0.0, "denseScore": 0.0})
            by_chunk[item.chunkId].update({"candidate": item, "sparseRank": item.sparseRank, "sparseScore": item.sparseScore})
        for item in dense:
            by_chunk.setdefault(item.chunkId, {"candidate": item, "sparseRank": None, "denseRank": None, "sparseScore": 0.0, "denseScore": 0.0})
            by_chunk[item.chunkId].update({"candidate": item, "denseRank": item.denseRank, "denseScore": item.denseScore})
        fused = []
        for chunk_id, value in by_chunk.items():
            sparse_rank = value["sparseRank"]
            dense_rank = value["denseRank"]
            score = 0.0
            if sparse_rank:
                score += self.sparse_weight / (self.rrf_k + sparse_rank)
            if dense_rank:
                score += self.dense_weight / (self.rrf_k + dense_rank)
            candidate = value["candidate"]
            fused.append(
                RetrievalCandidate(
                    retrieverType="hybrid-real",
                    tenantId=candidate.tenantId,
                    documentId=candidate.documentId,
                    chunkId=chunk_id,
                    sparseScore=float(value["sparseScore"]),
                    denseScore=float(value["denseScore"]),
                    sparseRank=sparse_rank,
                    denseRank=dense_rank,
                    rawRank=min([rank for rank in [sparse_rank, dense_rank] if rank] or [9999]),
                    fusionScore=round(score, 8),
                    row=candidate.row,
                )
            )
        fused.sort(key=lambda item: item.fusionScore, reverse=True)
        protected: list[RetrievalCandidate] = []
        seen: set[str] = set()
        for item in sparse[:fusion_top_k]:
            if item.chunkId not in seen:
                protected.append(item)
                seen.add(item.chunkId)
        for item in fused:
            if item.chunkId not in seen:
                protected.append(item)
                seen.add(item.chunkId)
            if len(protected) >= fusion_top_k:
                break
        return [RetrievalCandidate(**{**item.__dict__, "retrieverType": "hybrid-real", "fusionRank": rank}) for rank, item in enumerate(protected[:fusion_top_k], start=1)]

    @staticmethod
    def _rerank(query: str, candidates: list[RetrievalCandidate], top_k: int | None, *, tenant_id: str = "", evaluation_time_utc: str | None = None) -> list[RetrievalCandidate]:
        if not top_k:
            return candidates
        config = load_reranker_config()
        return GovernedReranker(config).rerank(query, candidates, top_k=top_k, tenant_id=tenant_id, evaluation_time_utc=evaluation_time_utc).candidates


def make_embedding_provider(provider_type: str, *, model_path: str = "", device: str = "cpu", batch_size: int = 8, max_length: int = 512, normalize: bool = True, load_on_startup: bool = False) -> BaseEmbeddingProvider:
    if provider_type == "hash":
        return HashEmbeddingProvider(normalize=normalize)
    if provider_type == "bge-m3":
        return make_bge_m3_provider(
            provider_impl=__import__("os").getenv("RAG_BGE_M3_PROVIDER_IMPL", "legacy-cls"),
            model_path=model_path,
            device=device,
            batch_size=batch_size,
            max_length=max_length,
            normalize=normalize,
            load_on_startup=load_on_startup,
            use_fp16=__import__("os").getenv("RAG_BGE_M3_USE_FP16", "false").lower() == "true",
        )
    if provider_type == "disabled":
        return DisabledEmbeddingProvider()
    raise ValueError("RAG_DENSE_PROVIDER_UNSUPPORTED")


def make_bge_m3_provider(
    *,
    provider_impl: str,
    model_path: str,
    device: str = "cpu",
    batch_size: int = 8,
    max_length: int = 512,
    normalize: bool = True,
    load_on_startup: bool = False,
    use_fp16: bool = False,
) -> BaseEmbeddingProvider:
    return _cached_bge_m3_provider(
        provider_impl=provider_impl,
        model_path=str(model_path),
        device=device,
        batch_size=batch_size,
        max_length=max_length,
        normalize=normalize,
        load_on_startup=load_on_startup,
        use_fp16=use_fp16,
    )


@lru_cache(maxsize=8)
def _cached_bge_m3_provider(
    *,
    provider_impl: str,
    model_path: str,
    device: str,
    batch_size: int,
    max_length: int,
    normalize: bool,
    load_on_startup: bool,
    use_fp16: bool,
) -> BaseEmbeddingProvider:
    config = BgeM3ProviderConfig(
        model_path=__import__("pathlib").Path(model_path),
        device=device,
        batch_size=batch_size,
        max_length=max_length,
        normalize=normalize,
        load_on_startup=load_on_startup,
        provider_impl=provider_impl,
        use_fp16=use_fp16,
    )
    if provider_impl == "legacy-cls":
        return BgeM3EmbeddingProvider(config)
    if provider_impl == "flagembedding":
        return OfficialBgeM3FlagProvider(config)
    if provider_impl == "sentence-transformers":
        return SentenceTransformerBgeM3Provider(config)
    raise ValueError("RAG_BGE_M3_PROVIDER_IMPL_UNSUPPORTED")


def _row_to_retriever(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "tenant_id": row["tenantId"],
        "document_id": row["documentId"],
        "document_version": row["documentVersion"],
        "chunk_id": row["chunkId"],
        "content": row["text"],
        "text": row["text"],
        "content_hash": row["contentHash"],
        "trust_level": "internal_verified",
        "active": row["status"] == "active",
        "deleted": row["status"] == "deleted",
        "source_type": row["sourceType"],
        "title": row["title"] or row["documentId"],
        "effective_from": row["effectiveFrom"],
        "effective_to": row["effectiveTo"],
        "visibility": row["visibility"],
    }
