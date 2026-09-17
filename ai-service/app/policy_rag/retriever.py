from __future__ import annotations

import hashlib
import math
import re
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Iterable

from app.core.config import settings
from app.observability.workflow_observer import NoopWorkflowObserver, WorkflowObserver
from app.policy_rag.chunker import PolicyStructureChunker
from app.policy_rag.embedding import PolicyEmbeddingProvider, create_policy_embedding_provider
from app.policy_rag.index_store import load_policy_chunks
from app.policy_rag.models import ParsedPolicyDocument, PolicyChunk, PolicySearchResult
from app.policy_rag.seeds import seed_policy_documents
from app.policy_rag.vector_store import DEFAULT_FAISS_META_NAME, DEFAULT_FAISS_NAME, PolicyFaissVectorStore


TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_§.-]+")


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for item in TOKEN_RE.findall(text or ""):
        term = item.lower().strip()
        if not term:
            continue
        tokens.append(term)
        if _is_cjk(term) and len(term) > 2:
            tokens.extend(term[index : index + 2] for index in range(0, len(term) - 1))
    return tokens


def _is_cjk(value: str) -> bool:
    return bool(value) and all("\u4e00" <= char <= "\u9fff" for char in value)


class PolicyEvidenceRetriever:
    def __init__(
        self,
        chunks: Iterable[PolicyChunk] | None = None,
        *,
        dense_store: PolicyFaissVectorStore | None = None,
        embedding_provider: PolicyEmbeddingProvider | None = None,
    ):
        default_index_path: Path | None = None
        policy_settings = settings.policy_rag
        self.enabled = policy_settings.enabled
        self.bm25_fallback_enabled = policy_settings.bm25_fallback_enabled
        if chunks is None:
            self.chunks, default_index_path = self._default_chunks_and_path()
        else:
            self.chunks = list(chunks)
        self._chunk_by_id = {chunk.chunkId: chunk for chunk in self.chunks}
        self._doc_freq = self._document_frequencies(self.chunks)
        self._doc_count = max(1, len(self.chunks))
        self.embedding_provider = embedding_provider
        self.dense_store = dense_store
        if self.dense_store is None and default_index_path is not None and policy_settings.dense_enabled:
            provider = embedding_provider or create_policy_embedding_provider()
            root = default_index_path.parent
            self.dense_store = PolicyFaissVectorStore(root / DEFAULT_FAISS_NAME, root / DEFAULT_FAISS_META_NAME, provider)
        self.last_fallback_used = False
        self.last_dense_error = ""
        self.overload_fallback_count = 0
        self.last_search_timings: dict[str, float | bool] = {}
        self._managed_enabled = chunks is None and bool(policy_settings.managed_index_root)
        self._managed_root_override: Path | None = None
        self._managed_version = "base"
        self._managed_desired_version = "base"
        self._managed_delegate: PolicyEvidenceRetriever | None = None
        self._managed_lock = threading.Lock()
        self._managed_reload_status = "ready"
        self._managed_last_reload_error = ""
        self._managed_last_reload_at = ""
        self._managed_failed_version = ""
        self._managed_retry_after = 0.0
        self._managed_load_count = 0

    @classmethod
    def from_documents(cls, documents: Iterable[ParsedPolicyDocument]) -> "PolicyEvidenceRetriever":
        chunker = PolicyStructureChunker()
        chunks: list[PolicyChunk] = []
        for document in documents:
            chunks.extend(chunker.chunk(document))
        return cls(chunks)

    @classmethod
    def from_jsonl(
        cls,
        path: Path | str,
        *,
        enable_dense: bool | None = None,
        embedding_provider: PolicyEmbeddingProvider | None = None,
    ) -> "PolicyEvidenceRetriever":
        chunks_path = cls._resolve_index_path(str(path))
        chunks = load_policy_chunks(chunks_path)
        dense_store = None
        dense_enabled = settings.policy_rag.dense_enabled if enable_dense is None else enable_dense
        if dense_enabled:
            provider = embedding_provider or create_policy_embedding_provider()
            root = chunks_path.parent
            dense_store = PolicyFaissVectorStore(root / DEFAULT_FAISS_NAME, root / DEFAULT_FAISS_META_NAME, provider)
        return cls(chunks, dense_store=dense_store, embedding_provider=embedding_provider)

    def search(
        self,
        query: str,
        *,
        risk_hints: list[str] | None = None,
        top_k: int = 3,
        mode: str = "hybrid",
        observer: WorkflowObserver | None = None,
    ) -> list[PolicySearchResult]:
        managed = self._managed_retriever()
        if managed is not None:
            results = managed.search(query, risk_hints=risk_hints, top_k=top_k, mode=mode, observer=observer)
            self._sync_managed_runtime(managed)
            return results
        runtime_observer = observer or NoopWorkflowObserver()
        with runtime_observer.span(
            "policy_retrieval",
            "retriever",
            input={"query": query},
            metadata={"requestedMode": mode, "topK": top_k, "riskTypes": risk_hints or []},
        ) as retrieval_span:
            if not self.enabled:
                self.last_fallback_used = True
                self.last_dense_error = "POLICY_RAG_DISABLED"
                retrieval_span.update(
                    output={"actualMode": "unavailable", "resultCount": 0},
                    metadata={"fallbackReason": self.last_dense_error},
                    status="fallback",
                )
                return []
            risk_hints = risk_hints or []
            expanded = " ".join([query, self._expand_risk_hints(risk_hints)]).strip()
            bm25_started = time.perf_counter()
            with runtime_observer.span("bm25", "span", metadata={"topK": max(top_k * 4, top_k)}) as bm25_span:
                bm25_ranked = self._bm25_search(expanded, risk_hints, top_k=max(top_k * 4, top_k))
                bm25_span.update(output={"resultCount": len(bm25_ranked)})
            bm25_ms = round((time.perf_counter() - bm25_started) * 1000, 2)
            if mode == "bm25":
                self.last_search_timings = {"bm25Ms": bm25_ms, "denseMs": 0.0, "faissSearchMs": 0.0, "rrfMs": 0.0, "cacheHit": False}
                results = [self._to_result(chunk, score, rank=index, mode="bm25_metadata_fallback") for index, (score, chunk) in enumerate(bm25_ranked[:top_k], start=1)]
                retrieval_span.update(output={"actualMode": "bm25_fallback", "resultCount": len(results)})
                return results
            dense_started = time.perf_counter()
            dense_ranked = self._dense_search(expanded, top_k=max(top_k * 4, top_k), observer=observer)
            dense_ms = round((time.perf_counter() - dense_started) * 1000, 2)
            dense_metrics = getattr(self.dense_store, "last_search_metrics", {}) if self.dense_store else {}
            if mode == "dense":
                dense_mode = "qwen_faiss_dense" if dense_ranked else "bm25_metadata_fallback"
                dense_results = dense_ranked[:top_k] if dense_ranked else self._fallback_results(bm25_ranked, top_k)
                self.last_search_timings = {"bm25Ms": bm25_ms, "denseMs": dense_ms, "faissSearchMs": dense_metrics.get("faissSearchMs", 0.0), "rrfMs": 0.0, "cacheHit": bool(dense_metrics.get("cacheHit", False))}
                results = [self._to_result(chunk, score, rank=index, mode=dense_mode) for index, (score, chunk) in enumerate(dense_results, start=1)]
                retrieval_span.update(
                    output={"actualMode": "dense" if dense_ranked else "bm25_fallback", "resultCount": len(results)},
                    metadata={"fallbackReason": self.last_dense_error, "cacheHit": bool(dense_metrics.get("cacheHit", False))},
                    status="success" if dense_ranked else "fallback",
                )
                return results
            fusion_started = time.perf_counter()
            with runtime_observer.span("rrf_fusion", "span", metadata={"topK": top_k}) as rrf_span:
                fused = self._fuse(bm25_ranked, dense_ranked, top_k=top_k) if dense_ranked else self._fallback_results(bm25_ranked, top_k)
                rrf_span.update(output={"resultCount": len(fused)}, status="success" if dense_ranked else "skipped")
            rrf_ms = round((time.perf_counter() - fusion_started) * 1000, 2)
            self.last_search_timings = {"bm25Ms": bm25_ms, "denseMs": dense_ms, "faissSearchMs": dense_metrics.get("faissSearchMs", 0.0), "rrfMs": rrf_ms, "cacheHit": bool(dense_metrics.get("cacheHit", False))}
            retrieval_mode = "hybrid_bm25_qwen_faiss_rrf" if dense_ranked else "bm25_metadata_fallback"
            results = [self._to_result(chunk, score, rank=index, mode=retrieval_mode) for index, (score, chunk) in enumerate(fused, start=1)]
            retrieval_span.update(
                output={"actualMode": "hybrid" if dense_ranked else "bm25_fallback", "resultCount": len(results)},
                metadata={
                    "fallbackReason": self.last_dense_error,
                    "cacheHit": bool(dense_metrics.get("cacheHit", False)),
                    "fallbackUsed": not bool(dense_ranked),
                },
                status="success" if dense_ranked else "fallback",
            )
            return results

    def readiness(self) -> dict[str, object]:
        managed = self._managed_retriever()
        if managed is not None:
            status = managed.readiness()
            status.update({
                "managed": True,
                "activeVersion": "" if self._managed_version == "base" else self._managed_version,
                "runtimeIndex": self._managed_runtime_status(managed),
            })
            return status
        dense_health = {"status": "disabled", "loaded": False, "reason": "dense retrieval disabled"}
        if self.dense_store is not None:
            provider_health = self.dense_store.provider.health()
            provider_status = provider_health.get("status")
            dense_health = {
                "status": "ready" if self.dense_store.available and provider_status in {"ready", "configured"} else "degraded",
                "indexAvailable": self.dense_store.available,
                "providerStatus": provider_status,
                "reason": "" if self.dense_store.available else "POLICY_FAISS_INDEX_NOT_AVAILABLE",
                "cache": self.dense_store.cache_stats(),
                "providerMetrics": self.dense_store.provider.metadata(),
            }
        bm25_ready = bool(self.chunks) and bool(self._doc_freq)
        retrieval_mode = "hybrid" if dense_health.get("status") == "ready" else ("bm25_fallback" if self.bm25_fallback_enabled and bm25_ready else "unavailable")
        status = {
            "enabled": self.enabled,
            "status": "ready" if self.enabled and retrieval_mode != "unavailable" else "degraded",
            "chunkCount": len(self.chunks),
            "bm25": {"status": "ready" if bm25_ready else "unavailable", "fallbackEnabled": self.bm25_fallback_enabled},
            "dense": dense_health,
            "retrievalMode": retrieval_mode,
            "fallbackAvailable": bool(self.bm25_fallback_enabled and bm25_ready),
            "lastFallbackUsed": self.last_fallback_used,
            "lastDenseError": self.last_dense_error,
            "overloadFallbackCount": self.overload_fallback_count,
        }
        if self._managed_enabled:
            status.update({
                "managed": True,
                "activeVersion": "" if self._managed_version == "base" else self._managed_version,
                "runtimeIndex": self._managed_runtime_status(None),
            })
        return status

    def observability_metadata(self) -> dict[str, object]:
        managed = self._managed_retriever()
        if managed is not None:
            return {
                **managed.observability_metadata(),
                "managedIndexVersion": self._managed_version,
                "desiredIndexVersion": self._managed_desired_version,
                "indexReloadStatus": self._managed_reload_status,
            }
        metadata: dict[str, object] = {
            "policyChunkCount": len(self.chunks),
            "policyIndexVersion": hashlib.sha256(
                "|".join(chunk.contentHash for chunk in self.chunks).encode("utf-8")
            ).hexdigest(),
        }
        if self.dense_store is not None:
            metadata.update(self.dense_store.observability_metadata())
        return metadata

    def chunk_for_id(self, chunk_id: str) -> PolicyChunk | None:
        """Resolve full policy text for internal ranking without widening citations."""
        managed = self._managed_retriever()
        if managed is not None:
            return managed.chunk_for_id(chunk_id)
        return self._chunk_by_id.get(chunk_id)

    def _managed_retriever(self) -> "PolicyEvidenceRetriever | None":
        if not self._managed_enabled:
            return None
        try:
            version = self._desired_managed_version()
        except Exception:
            self._managed_reload_status = "failed"
            self._managed_last_reload_error = "POLICY_INDEX_POINTER_INVALID"
            return self._managed_delegate
        self._managed_desired_version = version
        if version == self._managed_version:
            self._managed_reload_status = "ready"
            self._managed_last_reload_error = ""
            return self._managed_delegate
        if version == self._managed_failed_version and time.monotonic() < self._managed_retry_after:
            self._managed_reload_status = "failed"
            return self._managed_delegate

        # The request that wins the lock performs the load. Concurrent requests
        # keep serving the complete last-known-good retriever instead of waiting.
        if not self._managed_lock.acquire(blocking=False):
            self._managed_reload_status = "loading"
            return self._managed_delegate
        try:
            if version != self._desired_managed_version():
                self._managed_reload_status = "pending"
                return self._managed_delegate
            self._managed_reload_status = "loading"
            candidate = None if version == "base" else self._load_managed_version(version)
            self._managed_delegate = candidate
            self._managed_version = version
            self._managed_failed_version = ""
            self._managed_retry_after = 0.0
            self._managed_reload_status = "ready"
            self._managed_last_reload_error = ""
            self._managed_last_reload_at = self._utc_timestamp()
            self._managed_load_count += 1
            if candidate is not None:
                self._sync_managed_runtime(candidate)
            return candidate
        except Exception:
            self._managed_failed_version = version
            self._managed_retry_after = time.monotonic() + 5.0
            self._managed_reload_status = "failed"
            self._managed_last_reload_error = "POLICY_INDEX_RELOAD_FAILED"
            return self._managed_delegate
        finally:
            self._managed_lock.release()

    def _desired_managed_version(self) -> str:
        root = self._managed_root_override or self._resolve_managed_root(settings.policy_rag.managed_index_root)
        pointer = root / "ACTIVE"
        if not pointer.is_file():
            return "base"
        version = pointer.read_text(encoding="utf-8-sig").strip()
        if not re.fullmatch(r"policy-[0-9]{8}T[0-9]{6}-[0-9a-f]{8}", version):
            raise ValueError("POLICY_INDEX_POINTER_INVALID")
        return version

    def _load_managed_version(self, version: str) -> "PolicyEvidenceRetriever":
        root = self._managed_root_override or self._resolve_managed_root(settings.policy_rag.managed_index_root)
        directory = (root / "versions" / version).resolve()
        if not directory.is_relative_to(root.resolve()):
            raise ValueError("POLICY_INDEX_PATH_INVALID")
        chunks_path = directory / "policy_chunks.jsonl"
        if not chunks_path.is_file():
            raise FileNotFoundError("POLICY_INDEX_CHUNKS_NOT_AVAILABLE")
        provider = self.embedding_provider
        if provider is None and self.dense_store is not None:
            provider = self.dense_store.provider
        candidate = PolicyEvidenceRetriever.from_jsonl(
            chunks_path,
            enable_dense=settings.policy_rag.dense_enabled,
            embedding_provider=provider,
        )
        if not candidate.chunks:
            raise ValueError("POLICY_INDEX_EMPTY")
        if settings.policy_rag.dense_enabled and candidate.dense_store is not None and not candidate.dense_store.available:
            raise ValueError("POLICY_INDEX_DENSE_ARTIFACTS_NOT_AVAILABLE")
        if settings.policy_rag.dense_enabled and candidate.dense_store is not None:
            candidate.dense_store.ensure_loaded()
        return candidate

    def _managed_runtime_status(self, managed: "PolicyEvidenceRetriever | None") -> dict[str, object]:
        active = managed or self
        return {
            "desiredIndexVersion": self._managed_desired_version,
            "loadedIndexVersion": self._managed_version,
            "reloadStatus": self._managed_reload_status,
            "lastReloadError": self._managed_last_reload_error,
            "lastReloadAt": self._managed_last_reload_at,
            "loadedChunkCount": len(active.chunks),
            "loadCount": self._managed_load_count,
        }

    def active_dense_store(self) -> PolicyFaissVectorStore | None:
        managed = self._managed_retriever()
        return managed.dense_store if managed is not None else self.dense_store

    def _sync_managed_runtime(self, managed: "PolicyEvidenceRetriever") -> None:
        self.last_fallback_used = managed.last_fallback_used
        self.last_dense_error = managed.last_dense_error
        self.overload_fallback_count = managed.overload_fallback_count
        self.last_search_timings = dict(managed.last_search_timings)

    @staticmethod
    def _utc_timestamp() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _resolve_managed_root(value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (Path(__file__).resolve().parents[2] / path).resolve()

    def _bm25_search(self, query: str, risk_hints: list[str], *, top_k: int) -> list[tuple[float, PolicyChunk]]:
        if not self.bm25_fallback_enabled:
            return []
        query_terms = tokenize(query)
        scored: list[tuple[float, PolicyChunk]] = []
        for chunk in self.chunks:
            score = self._score(query_terms, chunk, risk_hints)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].chunkId))
        return scored[:top_k]

    def _dense_search(
        self,
        query: str,
        *,
        top_k: int,
        observer: WorkflowObserver | None = None,
    ) -> list[tuple[float, PolicyChunk]]:
        self.last_fallback_used = False
        self.last_dense_error = ""
        if not self.dense_store:
            self.last_fallback_used = True
            self.last_dense_error = "DENSE_STORE_NOT_CONFIGURED"
            return []
        try:
            dense_hits = (
                self.dense_store.search(query, top_k=top_k, observer=observer)
                if observer is not None
                else self.dense_store.search(query, top_k=top_k)
            )
        except Exception as exc:
            self.last_fallback_used = True
            if "EMBEDDING_QUEUE_TIMEOUT" in str(exc):
                self.last_dense_error = "OVERLOAD_FALLBACK"
                self.overload_fallback_count += 1
            else:
                self.last_dense_error = _safe_error_code(str(exc))
            return []
        ranked: list[tuple[float, PolicyChunk]] = []
        for hit in dense_hits:
            chunk = self._chunk_by_id.get(str(hit.get("chunkId", "")))
            if chunk:
                ranked.append((float(hit.get("denseScore", 0.0)), chunk))
        return ranked

    def _score(self, query_terms: list[str], chunk: PolicyChunk, risk_hints: list[str]) -> float:
        chunk_terms = Counter(tokenize(" ".join([chunk.heading, " ".join(chunk.sectionPath), chunk.text])))
        if not query_terms or not chunk_terms:
            return 0.0
        bm25 = 0.0
        length_norm = 1.0 + len(chunk_terms) / 120.0
        for term in query_terms:
            tf = chunk_terms.get(term, 0)
            if not tf:
                continue
            df = self._doc_freq.get(term, 0)
            idf = math.log(1 + (self._doc_count - df + 0.5) / (df + 0.5))
            bm25 += (tf / length_norm) * idf
        metadata_boost = 0.0
        for hint in risk_hints:
            if hint in chunk.riskTypes or hint in chunk.evidenceTags:
                metadata_boost += 2.0
        if chunk.sourceType in {"law", "regulation"}:
            metadata_boost += 0.25
        return round(bm25 + metadata_boost, 6)

    @staticmethod
    def _fuse(
        bm25_ranked: list[tuple[float, PolicyChunk]],
        dense_ranked: list[tuple[float, PolicyChunk]],
        *,
        top_k: int,
        k: int = 60,
    ) -> list[tuple[float, PolicyChunk]]:
        scores: dict[str, float] = {}
        chunks: dict[str, PolicyChunk] = {}
        for ranked in (bm25_ranked, dense_ranked):
            for rank, (_, chunk) in enumerate(ranked, start=1):
                scores[chunk.chunkId] = scores.get(chunk.chunkId, 0.0) + 1.0 / (k + rank)
                chunks[chunk.chunkId] = chunk
        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return [(round(score, 6), chunks[chunk_id]) for chunk_id, score in ordered[:top_k]]

    @staticmethod
    def _document_frequencies(chunks: list[PolicyChunk]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for chunk in chunks:
            for term in set(tokenize(" ".join([chunk.heading, " ".join(chunk.sectionPath), chunk.text]))):
                counts[term] = counts.get(term, 0) + 1
        return counts

    @staticmethod
    def _expand_risk_hints(risk_hints: list[str]) -> str:
        expansions = {
            "fake_review": "fake false fabricated misleading review 虚假评价 刷单 编造评价",
            "rating_manipulation": "paid review incentive cashback five star rating manipulation 好评返现 五星截图 评分操纵",
            "review_suppression": "delete remove suppress threaten unfavorable review 删除差评 屏蔽评价 压制负面反馈",
            "privacy_risk": "privacy personal information 隐私 个人信息",
            "after_sales_risk": "refund return broken after-sales 退款 退货 破损 售后 质量",
            "safety_or_fraud_risk": "unsafe fraud fake dangerous 安全 欺诈 假货 危险",
            "harassment_or_abuse": "harassment threat abuse 威胁 辱骂 骚扰",
        }
        return " ".join(expansions.get(item, item) for item in risk_hints)

    @staticmethod
    def _to_result(chunk: PolicyChunk, score: float, *, rank: int, mode: str) -> PolicySearchResult:
        snippet = re.sub(r"\s+", " ", chunk.text).strip()[:220]
        public_mode = "hybrid" if mode.startswith("hybrid") else ("dense" if "dense" in mode else "bm25_fallback")
        return PolicySearchResult(
            evidenceId=f"E{rank}",
            chunkId=chunk.chunkId,
            sourceType=chunk.sourceType,
            sourceName=chunk.sourceName,
            sourceUrl=chunk.sourceUrl,
            title=chunk.heading or chunk.sourceName,
            snippet=snippet,
            riskTypes=chunk.riskTypes,
            evidenceTags=chunk.evidenceTags,
            score=round(float(score), 6),
            contentHash=chunk.contentHash,
            sectionPath=chunk.sectionPath,
            clauseId=chunk.clauseId,
            licenseClass=chunk.licenseClass,
            retrievalMode=mode,
            retrieval={"mode": public_mode, "score": round(float(score), 6)},
        )

    @staticmethod
    def _default_chunks() -> list[PolicyChunk]:
        chunks, _ = PolicyEvidenceRetriever._default_chunks_and_path()
        return chunks

    @staticmethod
    def _default_chunks_and_path() -> tuple[list[PolicyChunk], Path | None]:
        policy_settings = settings.policy_rag
        if not policy_settings.enabled:
            return [], None
        index_path = policy_settings.index_path
        if index_path:
            try:
                resolved = PolicyEvidenceRetriever._resolve_index_path(index_path)
                return load_policy_chunks(resolved), resolved
            except Exception:
                if policy_settings.strict_index:
                    raise
        return [chunk for document in seed_policy_documents() for chunk in PolicyStructureChunker().chunk(document)], None

    @staticmethod
    def _resolve_index_path(index_path: str) -> Path:
        path = Path(index_path)
        if path.is_absolute() or path.exists():
            return path
        ai_root = Path(__file__).resolve().parents[2]
        repo_root = ai_root.parent
        for candidate in (ai_root / path, repo_root / path):
            if candidate.exists():
                return candidate
        return path

    def _fallback_results(self, bm25_ranked: list[tuple[float, PolicyChunk]], top_k: int) -> list[tuple[float, PolicyChunk]]:
        if not self.bm25_fallback_enabled:
            return []
        return bm25_ranked[:top_k]

def _safe_error_code(reason: str) -> str:
    if not reason:
        return ""
    upper = reason.upper()
    for marker in ("FAISS", "QWEN", "EMBEDDING", "DENSE", "INDEX"):
        if marker in upper:
            return f"POLICY_{marker}_UNAVAILABLE"
    return "POLICY_DENSE_RETRIEVAL_FAILED"
