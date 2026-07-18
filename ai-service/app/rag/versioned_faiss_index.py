from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class VersionedFaissManifest:
    index_version: str
    index_type: str
    embedding_model: str
    embedding_hash: str
    dimension: int
    vector_count: int
    metadata_count: int
    checksum: str
    built_at: str
    active: bool = False


class VersionedFaissIndex:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.versions = self.root / "versions"
        self.active_pointer = self.root / "ACTIVE"
        self.versions.mkdir(parents=True, exist_ok=True)

    def build_staging(self, vectors: np.ndarray, metadata: list[dict[str, Any]], embedding_model: str, embedding_hash: str) -> VersionedFaissManifest:
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("FAISS_NOT_AVAILABLE") from exc
        matrix = np.asarray(vectors, dtype="float32")
        if matrix.ndim != 2:
            raise ValueError("FAISS_VECTOR_RANK_INVALID")
        if len(metadata) != matrix.shape[0]:
            raise ValueError("FAISS_METADATA_VECTOR_COUNT_MISMATCH")
        if not np.isfinite(matrix).all():
            raise ValueError("FAISS_VECTOR_NAN_OR_INF")
        faiss.normalize_L2(matrix)
        dimension = int(matrix.shape[1])
        index = faiss.IndexFlatIP(dimension)
        index.add(matrix)
        version = datetime.now(timezone.utc).strftime("bge-m3-%Y%m%dT%H%M%S%fZ")
        staging = self.versions / f"{version}.staging"
        staging.mkdir(parents=True, exist_ok=False)
        index_path = staging / "index.faiss"
        meta_path = staging / "metadata.jsonl"
        index_path.write_bytes(faiss.serialize_index(index).tobytes())
        meta_path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in metadata) + "\n", encoding="utf-8")
        checksum = self._checksum(index_path, meta_path)
        manifest = VersionedFaissManifest(
            index_version=version,
            index_type="IndexFlatIP",
            embedding_model=embedding_model,
            embedding_hash=embedding_hash,
            dimension=dimension,
            vector_count=int(index.ntotal),
            metadata_count=len(metadata),
            checksum=checksum,
            built_at=datetime.now(timezone.utc).isoformat(),
        )
        (staging / "manifest.json").write_text(json.dumps(manifest.__dict__, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        return manifest

    def publish(self, index_version: str) -> VersionedFaissManifest:
        staging = self.versions / f"{index_version}.staging"
        final = self.versions / index_version
        if not staging.exists():
            raise RuntimeError("FAISS_STAGING_VERSION_NOT_FOUND")
        if final.exists():
            raise RuntimeError("FAISS_VERSION_ALREADY_EXISTS")
        staging.rename(final)
        manifest = self._read_manifest(final)
        manifest = VersionedFaissManifest(**{**manifest.__dict__, "active": True})
        (final / "manifest.json").write_text(json.dumps(manifest.__dict__, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        tmp_pointer = self.root / "ACTIVE.tmp"
        tmp_pointer.write_text(index_version + "\n", encoding="utf-8", newline="\n")
        tmp_pointer.replace(self.active_pointer)
        return manifest

    def active_version(self) -> str | None:
        if not self.active_pointer.exists():
            return None
        value = self.active_pointer.read_text(encoding="utf-8").strip()
        return value or None

    def load_active(self) -> tuple[Any, list[dict[str, Any]], VersionedFaissManifest]:
        version = self.active_version()
        if not version:
            raise RuntimeError("FAISS_ACTIVE_VERSION_NOT_FOUND")
        version_dir = self.versions / version
        manifest = self._read_manifest(version_dir)
        if self._checksum(version_dir / "index.faiss", version_dir / "metadata.jsonl") != manifest.checksum:
            raise RuntimeError("FAISS_INDEX_CHECKSUM_MISMATCH")
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("FAISS_NOT_AVAILABLE") from exc
        index = faiss.deserialize_index(np.frombuffer((version_dir / "index.faiss").read_bytes(), dtype="uint8"))
        rows = [json.loads(line) for line in (version_dir / "metadata.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if index.ntotal != len(rows):
            raise RuntimeError("FAISS_INDEX_METADATA_MISMATCH")
        return index, rows, manifest

    def rollback(self, index_version: str) -> VersionedFaissManifest:
        version_dir = self.versions / index_version
        if not version_dir.exists():
            raise RuntimeError("FAISS_ROLLBACK_VERSION_NOT_FOUND")
        tmp_pointer = self.root / "ACTIVE.tmp"
        tmp_pointer.write_text(index_version + "\n", encoding="utf-8", newline="\n")
        tmp_pointer.replace(self.active_pointer)
        return self._read_manifest(version_dir)

    def cleanup_staging(self) -> int:
        count = 0
        for path in self.versions.glob("*.staging"):
            if path.is_dir():
                shutil.rmtree(path)
                count += 1
        return count

    @staticmethod
    def _checksum(*paths: Path) -> str:
        digest = hashlib.sha256()
        for path in paths:
            digest.update(path.read_bytes())
        return digest.hexdigest()

    @staticmethod
    def _read_manifest(version_dir: Path) -> VersionedFaissManifest:
        return VersionedFaissManifest(**json.loads((version_dir / "manifest.json").read_text(encoding="utf-8")))
