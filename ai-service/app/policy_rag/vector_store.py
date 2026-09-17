from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from app.policy_rag.embedding import PolicyEmbeddingProvider
from app.core.config import settings
from app.observability.workflow_observer import NoopWorkflowObserver, WorkflowObserver
from app.policy_rag.models import PolicyChunk, utc_now
from app.rag.document_contract import stable_hash


DEFAULT_FAISS_NAME = "policy_vectors.faiss"
DEFAULT_FAISS_META_NAME = "policy_vectors_meta.json"


def build_policy_faiss_index(
    chunks: list[PolicyChunk],
    *,
    output_dir: Path | str,
    provider: PolicyEmbeddingProvider,
    reuse_dir: Path | str | None = None,
) -> dict[str, Any]:
    target_dir = Path(output_dir)
    index_path = target_dir / DEFAULT_FAISS_NAME
    meta_path = target_dir / DEFAULT_FAISS_META_NAME
    if not chunks:
        return _disabled("DENSE_EMPTY_CHUNKS")
    try:
        import faiss

        reusable, reuse_metadata = _reusable_vectors(reuse_dir, provider)
        pending_indexes = [index for index, chunk in enumerate(chunks) if chunk.contentHash not in reusable]
        embedded = np.empty((0, 0), dtype="float32")
        if pending_indexes:
            embedded = np.asarray(provider.embed_documents([chunks[index].text for index in pending_indexes]), dtype="float32")
        old_dimension = int(reuse_metadata.get("dimension", 0) or 0)
        new_dimension = int(embedded.shape[1]) if embedded.ndim == 2 and embedded.shape[0] else 0
        if reusable and new_dimension and old_dimension != new_dimension:
            reusable = {}
            reuse_metadata = {"status": "incompatible", "reason": "DENSE_REUSE_DIMENSION_MISMATCH"}
            pending_indexes = list(range(len(chunks)))
            embedded = np.asarray(provider.embed_documents([chunk.text for chunk in chunks]), dtype="float32")
            new_dimension = int(embedded.shape[1])
        dimension = new_dimension or old_dimension
        if dimension <= 0:
            raise ValueError("DENSE_VECTOR_DIMENSION_INVALID")
        matrix = np.empty((len(chunks), dimension), dtype="float32")
        embedded_cursor = 0
        reused_count = 0
        for index, chunk in enumerate(chunks):
            vector = reusable.get(chunk.contentHash)
            if vector is not None:
                matrix[index] = vector
                reused_count += 1
            else:
                matrix[index] = embedded[embedded_cursor]
                embedded_cursor += 1
        if matrix.ndim != 2 or matrix.shape[0] != len(chunks):
            raise ValueError("DENSE_VECTOR_SHAPE_INVALID")
        if not np.isfinite(matrix).all():
            raise ValueError("DENSE_VECTOR_NAN_OR_INF")
        dimension = int(matrix.shape[1])
        index = faiss.IndexFlatIP(dimension)
        index.add(matrix)
        target_dir.mkdir(parents=True, exist_ok=True)
        index_path.write_bytes(faiss.serialize_index(index).tobytes())
        rows = [_metadata_row(position, chunk) for position, chunk in enumerate(chunks)]
        provider_metadata = provider.metadata()
        if reused_count == len(chunks) and isinstance(reuse_metadata.get("provider"), dict):
            provider_metadata = dict(reuse_metadata["provider"])
        old_hashes = set(reuse_metadata.get("contentHashes") or [])
        current_hashes = {chunk.contentHash for chunk in chunks}
        incremental = {
            "status": reuse_metadata.get("status", "not_available"),
            "reusedVectorCount": reused_count,
            "embeddedVectorCount": len(chunks) - reused_count,
            "removedVectorCount": len(old_hashes - current_hashes),
            "sourceVectorCount": int(reuse_metadata.get("vectorCount", 0) or 0),
        }
        meta = {
            "schemaVersion": "policy-rag-faiss-v1",
            "status": "ready",
            "builtAt": utc_now(),
            "indexPath": str(index_path),
            "metaPath": str(meta_path),
            "vectorCount": int(index.ntotal),
            "chunkCount": len(chunks),
            "dimension": dimension,
            "indexType": "IndexFlatIP",
            "metric": "inner-product",
            "provider": provider_metadata,
            "incremental": incremental,
            "contentRootHash": stable_hash({"chunks": [chunk.contentHash for chunk in chunks]}),
            "rows": rows,
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        return {key: value for key, value in meta.items() if key != "rows"}
    except Exception as exc:
        return _disabled(str(exc)[:240])


def _reusable_vectors(reuse_dir: Path | str | None, provider: PolicyEmbeddingProvider) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    if not reuse_dir:
        return {}, {"status": "not_available"}
    directory = Path(reuse_dir)
    index_path = directory / DEFAULT_FAISS_NAME
    meta_path = directory / DEFAULT_FAISS_META_NAME
    if not index_path.is_file() or not meta_path.is_file():
        return {}, {"status": "not_available"}
    try:
        import faiss

        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        old_provider = meta.get("provider") if isinstance(meta.get("provider"), dict) else {}
        if not _compatible_provider(old_provider, provider.metadata()):
            return {}, {"status": "incompatible", "reason": "DENSE_REUSE_PROVIDER_MISMATCH"}
        index = faiss.deserialize_index(np.frombuffer(index_path.read_bytes(), dtype="uint8"))
        rows = meta.get("rows") or []
        if int(index.ntotal) != len(rows) or int(index.ntotal) != int(meta.get("vectorCount", -1)):
            return {}, {"status": "invalid", "reason": "DENSE_REUSE_COUNT_MISMATCH"}
        matrix = np.asarray(index.reconstruct_n(0, int(index.ntotal)), dtype="float32")
        reusable: dict[str, np.ndarray] = {}
        content_hashes: list[str] = []
        for row, vector in zip(rows, matrix):
            content_hash = str(row.get("contentHash") or "")
            if content_hash:
                reusable.setdefault(content_hash, vector)
                content_hashes.append(content_hash)
        return reusable, {
            "status": "ready",
            "vectorCount": int(index.ntotal),
            "dimension": int(index.d),
            "provider": old_provider,
            "contentHashes": content_hashes,
        }
    except Exception as exc:
        return {}, {"status": "invalid", "reason": type(exc).__name__}


def _compatible_provider(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    identity_fields = (
        "providerType",
        "modelName",
        "normalize",
        "pooling",
        "maxLength",
        "embeddingProfile",
        "queryInstructionHash",
    )
    return bool(previous) and all(previous.get(field) == current.get(field) for field in identity_fields)


class PolicyFaissVectorStore:
    def __init__(self, index_path: Path | str, meta_path: Path | str, provider: PolicyEmbeddingProvider):
        self.index_path = Path(index_path)
        self.meta_path = Path(meta_path)
        self.provider = provider
        self._index: Any = None
        self._meta: dict[str, Any] | None = None
        self._load_lock = threading.Lock()
        self._query_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._cache_lock = threading.Lock()
        self.last_search_metrics: dict[str, float | bool] = {}

    @property
    def available(self) -> bool:
        return self.index_path.exists() and self.meta_path.exists()

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        observer: WorkflowObserver | None = None,
    ) -> list[dict[str, Any]]:
        started = time.perf_counter()
        runtime_observer = observer or NoopWorkflowObserver()
        if not self.available:
            raise RuntimeError("POLICY_FAISS_INDEX_NOT_AVAILABLE")
        with runtime_observer.span("faiss_index_load", "span") as span:
            loaded_now = self.ensure_loaded()
            span.update(
                output={"vectorCount": int(self._index.ntotal), "dimension": int(self._index.d)},
                metadata={"loadedNow": loaded_now},
                status="success" if loaded_now else "skipped",
            )
        cache_key = self._cache_key(query, top_k)
        with self._cache_lock:
            cached = self._query_cache.get(cache_key) if settings.policy_rag.query_cache_enabled else None
            valid_cached = isinstance(cached, tuple) and len(cached) == 2 and isinstance(cached[0], (float, int)) and isinstance(cached[1], list)
            if cached and not valid_cached:
                self._query_cache.pop(cache_key, None)
                cached = None
            if cached and cached[0] >= time.time():
                self._cache_hits += 1
        if cached:
            self.last_search_metrics = {
                "cacheHit": True,
                "embeddingMs": 0.0,
                "faissSearchMs": 0.0,
                "totalMs": round((time.perf_counter() - started) * 1000, 2),
            }
            with runtime_observer.span("dense_query_cache", "span", metadata={"cacheHit": True}) as span:
                span.update(output={"resultCount": len(cached[1])})
            return [dict(item) for item in cached[1]]
        with self._cache_lock:
            self._cache_misses += 1
        embedding_started = time.perf_counter()
        with runtime_observer.span("dense_embedding", "embedding", input={"query": query}) as span:
            observed_embed = getattr(self.provider, "embed_query_observed", None)
            embedded = (
                observed_embed(query, runtime_observer)
                if callable(observed_embed) and observer is not None
                else self.provider.embed_query(query)
            )
            vector = np.asarray(embedded, dtype="float32")
            provider_metrics = self.provider.metadata()
            span.update(
                output={"dimension": int(vector.shape[1]) if vector.ndim == 2 else 0},
                metadata={
                    "queueWaitMs": provider_metrics.get("queueWaitMs", 0),
                    "embeddingComputeMs": provider_metrics.get("embeddingComputeMs", provider_metrics.get("lastEmbeddingLatencyMs", 0)),
                    "cacheHit": False,
                },
            )
        embedding_ms = round((time.perf_counter() - embedding_started) * 1000, 2)
        if vector.ndim != 2 or vector.shape[0] != 1:
            raise ValueError("POLICY_FAISS_QUERY_VECTOR_SHAPE_INVALID")
        faiss_started = time.perf_counter()
        with runtime_observer.span("faiss_search", "span", metadata={"topK": top_k}) as span:
            scores, indexes = self._index.search(vector, min(max(top_k, 1), self._index.ntotal))
            span.update(output={"resultCount": int(sum(1 for item in indexes[0] if item >= 0))})
        faiss_ms = round((time.perf_counter() - faiss_started) * 1000, 2)
        rows = self._meta.get("rows") or []
        hits: list[dict[str, Any]] = []
        for rank, (score, index) in enumerate(zip(scores[0], indexes[0]), start=1):
            if index < 0:
                continue
            row = dict(rows[int(index)])
            row.update({"denseScore": float(score), "denseRank": rank})
            hits.append(row)
        if settings.policy_rag.query_cache_enabled:
            with self._cache_lock:
                self._query_cache[cache_key] = (time.time() + settings.policy_rag.query_cache_ttl_seconds, [dict(item) for item in hits])
        self.last_search_metrics = {
            "cacheHit": False,
            "embeddingMs": embedding_ms,
            "faissSearchMs": faiss_ms,
            "totalMs": round((time.perf_counter() - started) * 1000, 2),
        }
        return hits

    def ensure_loaded(self) -> bool:
        """Load and validate the persisted index once; return whether this call loaded it."""
        if self._index is not None and self._meta is not None:
            return False
        if not self.available:
            raise RuntimeError("POLICY_FAISS_INDEX_NOT_AVAILABLE")
        with self._load_lock:
            if self._index is not None and self._meta is not None:
                return False
            import faiss

            index = faiss.deserialize_index(np.frombuffer(self.index_path.read_bytes(), dtype="uint8"))
            meta = json.loads(self.meta_path.read_text(encoding="utf-8-sig"))
            rows = meta.get("rows") or []
            if int(index.ntotal) != int(meta.get("vectorCount", -1)) or int(index.ntotal) != len(rows):
                raise RuntimeError("POLICY_FAISS_VECTOR_COUNT_MISMATCH")
            if int(index.d) != int(meta.get("dimension", -1)):
                raise RuntimeError("POLICY_FAISS_DIMENSION_MISMATCH")
            self._index = index
            self._meta = meta
            return True

    def cache_stats(self) -> dict[str, int]:
        with self._cache_lock:
            return {"hits": self._cache_hits, "misses": self._cache_misses, "size": len(self._query_cache)}

    def clear_query_cache(self) -> None:
        """Clear only transient query vectors; the persisted FAISS index is untouched."""
        with self._cache_lock:
            self._query_cache.clear()

    def observability_metadata(self) -> dict[str, Any]:
        """Return stable index/model identity without exposing local model paths."""
        manifest = self._meta
        if manifest is None and self.meta_path.exists():
            try:
                manifest = json.loads(self.meta_path.read_text(encoding="utf-8-sig"))
            except Exception:
                manifest = {}
        manifest = manifest or {}
        provider = self.provider.metadata()
        return {
            "policyIndexVersion": str(manifest.get("contentRootHash", "")),
            "vectorCount": int(manifest.get("vectorCount", 0) or 0),
            "embeddingDimension": int(provider.get("dimension", manifest.get("dimension", 0)) or 0),
            "embeddingProvider": str(provider.get("providerType", "")),
            "embeddingModel": str(provider.get("modelName", "")),
            "embeddingModelFingerprint": str(provider.get("modelFingerprint", "")),
        }

    def _cache_key(self, query: str, top_k: int) -> str:
        provider = self.provider.metadata()
        index_version = (self._meta or {}).get("contentRootHash", "")
        normalized = " ".join((query or "").lower().split())
        model_identity = "|".join(
            str(provider.get(key, ""))
            for key in (
                "providerType",
                "modelName",
                "modelPath",
                "pooling",
                "normalize",
                "maxLength",
                "queryInstructionHash",
                "modelFingerprint",
            )
        )
        material = f"{index_version}|{model_identity}|{top_k}|{normalized}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _metadata_row(position: int, chunk: PolicyChunk) -> dict[str, Any]:
    return {
        "vectorPosition": position,
        "chunkId": chunk.chunkId,
        "documentId": chunk.documentId,
        "contentHash": chunk.contentHash,
        "sourceName": chunk.sourceName,
        "sourceUrl": chunk.sourceUrl,
        "sourceType": chunk.sourceType,
        "sectionPath": chunk.sectionPath,
        "clauseId": chunk.clauseId,
        "riskTypes": chunk.riskTypes,
        "evidenceTags": chunk.evidenceTags,
    }


def _disabled(reason: str) -> dict[str, Any]:
    return {
        "schemaVersion": "policy-rag-faiss-v1",
        "status": "disabled",
        "builtAt": utc_now(),
        "fallbackReason": reason,
    }
