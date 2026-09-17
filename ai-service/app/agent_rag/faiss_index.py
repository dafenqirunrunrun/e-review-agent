from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.agent_rag.embedding_provider import BaseEmbeddingProvider
from app.agent_rag.knowledge import IndexStatus, KnowledgeChunk, utc_now
from app.agent_rag.observability import metrics_registry
from app.rag.document_contract import stable_hash
from app.rag.tenant_acl import normalize_tenant_id


class IndexCompatibilityError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FaissManifest:
    indexVersion: str
    tenantId: str
    status: str
    denseProvider: str
    modelName: str
    modelFingerprint: str
    embeddingDimension: int
    normalize: bool
    faissIndexType: str
    faissMetric: str
    vectorCount: int
    documentCount: int
    chunkCount: int
    indexFileSha256: str
    metadataFileSha256: str
    configHash: str
    contentRootHash: str
    sourceCommit: str
    createdAt: str
    activatedAt: str | None = None
    assetFingerprint: str = ""
    providerFingerprint: str = ""
    effectiveEmbeddingFingerprint: str = ""
    providerImpl: str = ""
    providerConformance: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class FaissVectorIndex:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.versions = self.root / "versions"
        self.active_pointer = self.root / "ACTIVE"
        self.previous_pointer = self.root / "PREVIOUS"
        self.versions.mkdir(parents=True, exist_ok=True)
        self.last_load_ms = 0
        self.last_search_ms = 0
        self.last_load_ns = 0
        self.last_search_ns = 0
        self._swap_lock = threading.RLock()

    def build(
        self,
        *,
        chunks: list[KnowledgeChunk],
        provider: BaseEmbeddingProvider,
        tenant_id: str,
        index_version: str,
        source_commit: str = "local",
    ) -> FaissManifest:
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("FAISS_NOT_AVAILABLE") from exc
        tenant = normalize_tenant_id(tenant_id)
        texts = [chunk.text for chunk in chunks]
        if not texts:
            raise ValueError("FAISS_EMPTY_CHUNKS")
        vectors = provider.embed_documents(texts)
        matrix = np.asarray(vectors, dtype="float32")
        if matrix.ndim != 2 or matrix.shape[0] != len(chunks):
            raise ValueError("FAISS_VECTOR_SHAPE_INVALID")
        if not np.isfinite(matrix).all():
            raise ValueError("FAISS_VECTOR_NAN_OR_INF")
        meta = provider.metadata()
        dimension = int(matrix.shape[1])
        if int(meta["dimension"]) != dimension:
            raise IndexCompatibilityError("EMBEDDING_DIMENSION_MISMATCH")
        index = faiss.IndexFlatIP(dimension)
        index.add(matrix)
        version_dir = self.versions / index_version
        staging = self.versions / f"{index_version}.staging"
        if version_dir.exists() or staging.exists():
            raise RuntimeError("FAISS_INDEX_VERSION_ALREADY_EXISTS")
        staging.mkdir(parents=True)
        metadata_rows = [_metadata_row(position, chunk) for position, chunk in enumerate(chunks)]
        index_path = staging / "index.faiss"
        metadata_path = staging / "metadata.jsonl"
        manifest_path = staging / "manifest.json"
        index_path.write_bytes(faiss.serialize_index(index).tobytes())
        metadata_path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in metadata_rows) + "\n", encoding="utf-8", newline="\n")
        manifest = FaissManifest(
            indexVersion=index_version,
            tenantId=tenant,
            status=IndexStatus.ready.value,
            denseProvider=str(meta["providerType"]),
            modelName=str(meta["modelName"]),
            modelFingerprint=str(meta["modelFingerprint"]),
            assetFingerprint=str(meta.get("assetFingerprint", "")),
            providerFingerprint=str(meta.get("providerFingerprint", "")),
            effectiveEmbeddingFingerprint=str(meta.get("effectiveEmbeddingFingerprint", meta["modelFingerprint"])),
            providerImpl=str(meta.get("providerImpl", "")),
            providerConformance=str(meta.get("providerConformance", "")),
            embeddingDimension=dimension,
            normalize=bool(meta["normalize"]),
            faissIndexType="IndexFlatIP",
            faissMetric="inner-product",
            vectorCount=int(index.ntotal),
            documentCount=len({chunk.documentId for chunk in chunks}),
            chunkCount=len(chunks),
            indexFileSha256=_sha256(index_path),
            metadataFileSha256=_sha256(metadata_path),
            configHash=stable_hash({"denseProvider": meta["providerType"], "providerImpl": meta.get("providerImpl", ""), "effectiveEmbeddingFingerprint": meta.get("effectiveEmbeddingFingerprint", meta["modelFingerprint"]), "dimension": dimension, "normalize": meta["normalize"], "faiss": "IndexFlatIP"}),
            contentRootHash=stable_hash({"chunks": [chunk.contentHash for chunk in chunks]}),
            sourceCommit=source_commit,
            createdAt=utc_now(),
        )
        manifest_path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        staging.rename(version_dir)
        return manifest

    def validate_candidate(self, index_version: str, provider_metadata: dict[str, Any], *, tenant_id: str) -> FaissManifest:
        manifest, rows = self._read_version(index_version)
        self._validate_manifest(manifest, rows, provider_metadata, tenant_id=tenant_id)
        return manifest

    def activate(self, index_version: str, provider_metadata: dict[str, Any], *, tenant_id: str) -> FaissManifest:
        with self._swap_lock:
            manifest = self.validate_candidate(index_version, provider_metadata, tenant_id=tenant_id)
            current = self.active_version()
            if current and current != index_version:
                _atomic_write(self.previous_pointer, current + "\n")
            activated = FaissManifest(**{**manifest.to_dict(), "status": IndexStatus.active.value, "activatedAt": utc_now()})
            version_dir = self.versions / index_version
            (version_dir / "manifest.json").write_text(json.dumps(activated.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            _atomic_write(self.active_pointer, index_version + "\n")
            metrics_registry.increment("index_hot_swap_total")
            return activated

    def rollback(self, provider_metadata: dict[str, Any], *, tenant_id: str, previous_version: str | None = None) -> FaissManifest:
        target = previous_version or (self.previous_pointer.read_text(encoding="utf-8").strip() if self.previous_pointer.exists() else "")
        if not target:
            raise IndexCompatibilityError("ROLLBACK_VERSION_NOT_FOUND")
        return self.activate(target, provider_metadata, tenant_id=tenant_id)

    def active_version(self) -> str | None:
        if not self.active_pointer.exists():
            return None
        value = self.active_pointer.read_text(encoding="utf-8").strip()
        return value or None

    def load_active(self, provider_metadata: dict[str, Any], *, tenant_id: str) -> tuple[Any, list[dict[str, Any]], FaissManifest]:
        with self._swap_lock:
            started = time.perf_counter_ns()
            version = self.active_version()
            if not version:
                raise IndexCompatibilityError("ACTIVE_INDEX_NOT_FOUND")
            manifest, rows = self._read_version(version)
            self._validate_manifest(manifest, rows, provider_metadata, tenant_id=tenant_id)
            try:
                import faiss
            except ImportError as exc:
                raise RuntimeError("FAISS_NOT_AVAILABLE") from exc
            index = faiss.deserialize_index(np.frombuffer((self.versions / version / "index.faiss").read_bytes(), dtype="uint8"))
            if index.ntotal != len(rows):
                raise IndexCompatibilityError("INDEX_METADATA_COUNT_MISMATCH")
            self.last_load_ns = time.perf_counter_ns() - started
            self.last_load_ms = round(self.last_load_ns / 1_000_000, 3)
            metrics_registry.observe("index_load_latency_ms", self.last_load_ms)
            return index, rows, manifest

    def search(self, query_vector: np.ndarray, provider_metadata: dict[str, Any], *, tenant_id: str, top_k: int = 20) -> tuple[list[dict[str, Any]], FaissManifest]:
        index, rows, manifest = self.load_active(provider_metadata, tenant_id=tenant_id)
        vector = np.asarray(query_vector, dtype="float32")
        if vector.ndim != 2 or vector.shape[0] != 1:
            raise ValueError("FAISS_QUERY_VECTOR_SHAPE_INVALID")
        started = time.perf_counter_ns()
        scores, ids = index.search(vector, max(top_k * 4, top_k))
        self.last_search_ns = time.perf_counter_ns() - started
        self.last_search_ms = round(self.last_search_ns / 1_000_000, 3)
        metrics_registry.observe("faiss_search_latency_ms", self.last_search_ms)
        tenant = normalize_tenant_id(tenant_id)
        hits: list[dict[str, Any]] = []
        rank = 1
        for score, row_id in zip(scores[0], ids[0]):
            if row_id < 0:
                continue
            row = rows[int(row_id)]
            if row.get("tenantId") not in {tenant, "__public__"}:
                continue
            if row.get("status") != "active":
                continue
            result = dict(row)
            result.update({"denseScore": round(float(score), 6), "denseRank": rank, "indexVersion": manifest.indexVersion, "modelFingerprint": manifest.modelFingerprint, "providerType": manifest.denseProvider})
            hits.append(result)
            rank += 1
            if len(hits) >= top_k:
                break
        return hits, manifest

    def _read_version(self, index_version: str) -> tuple[FaissManifest, list[dict[str, Any]]]:
        version_dir = self.versions / index_version
        if not version_dir.exists():
            raise IndexCompatibilityError("INDEX_VERSION_NOT_FOUND")
        manifest_path = version_dir / "manifest.json"
        metadata_path = version_dir / "metadata.jsonl"
        index_path = version_dir / "index.faiss"
        if not manifest_path.exists() or not metadata_path.exists() or not index_path.exists():
            raise IndexCompatibilityError("MANIFEST_OR_INDEX_FILE_MISSING")
        manifest = FaissManifest(**json.loads(manifest_path.read_text(encoding="utf-8")))
        rows = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return manifest, rows

    def _validate_manifest(self, manifest: FaissManifest, rows: list[dict[str, Any]], provider_metadata: dict[str, Any], *, tenant_id: str) -> None:
        version_dir = self.versions / manifest.indexVersion
        if manifest.status not in {IndexStatus.ready.value, IndexStatus.active.value}:
            raise IndexCompatibilityError("INDEX_STATUS_NOT_READY")
        if manifest.tenantId != normalize_tenant_id(tenant_id):
            raise IndexCompatibilityError("TENANT_MISMATCH")
        if manifest.modelFingerprint != provider_metadata.get("modelFingerprint"):
            raise IndexCompatibilityError("MODEL_FINGERPRINT_MISMATCH")
        if manifest.effectiveEmbeddingFingerprint and manifest.effectiveEmbeddingFingerprint != provider_metadata.get("effectiveEmbeddingFingerprint"):
            raise IndexCompatibilityError("EFFECTIVE_EMBEDDING_FINGERPRINT_MISMATCH")
        if manifest.providerImpl and manifest.providerImpl != provider_metadata.get("providerImpl"):
            raise IndexCompatibilityError("PROVIDER_IMPL_MISMATCH")
        if manifest.embeddingDimension != int(provider_metadata.get("dimension") or 0):
            raise IndexCompatibilityError("EMBEDDING_DIMENSION_MISMATCH")
        if manifest.normalize != bool(provider_metadata.get("normalize")):
            raise IndexCompatibilityError("NORMALIZE_SETTING_MISMATCH")
        if manifest.faissIndexType != "IndexFlatIP" or manifest.faissMetric != "inner-product":
            raise IndexCompatibilityError("FAISS_INDEX_CONFIG_MISMATCH")
        if manifest.vectorCount != len(rows) or manifest.chunkCount != len(rows):
            raise IndexCompatibilityError("INDEX_METADATA_COUNT_MISMATCH")
        if manifest.indexFileSha256 != _sha256(version_dir / "index.faiss") or manifest.metadataFileSha256 != _sha256(version_dir / "metadata.jsonl"):
            raise IndexCompatibilityError("INDEX_CHECKSUM_MISMATCH")


class HashFixtureVectorIndex:
    def __init__(self, chunks: list[KnowledgeChunk]):
        self.chunks = chunks

    def search(self, query: str, *, tenant_id: str, top_k: int = 20) -> list[dict[str, Any]]:
        from app.agent_rag.phase2_retrieval import RrfHybridRetriever

        candidates, _ = RrfHybridRetriever(self.chunks, mode="dense-only").search(query, tenant_id=tenant_id, dense_top_k=top_k, fusion_top_k=top_k)
        return [candidate.row or {} for candidate in candidates]


def _metadata_row(position: int, chunk: KnowledgeChunk) -> dict[str, Any]:
    return {
        "vectorPosition": position,
        "chunkId": chunk.chunkId,
        "documentId": chunk.documentId,
        "tenantId": chunk.tenantId,
        "contentHash": chunk.contentHash,
        "documentVersion": chunk.documentVersion,
        "status": chunk.status.value if hasattr(chunk.status, "value") else str(chunk.status),
        "effectiveFrom": chunk.effectiveFrom,
        "effectiveTo": chunk.effectiveTo,
        "sourceType": chunk.sourceType.value if hasattr(chunk.sourceType, "value") else str(chunk.sourceType),
        "title": chunk.title,
        "text": chunk.text,
        "visibility": chunk.visibility,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    os.replace(tmp, path)
