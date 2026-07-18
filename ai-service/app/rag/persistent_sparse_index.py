from __future__ import annotations

import json
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.rag.sparse_retriever import BM25Retriever, tokenize


@dataclass(frozen=True)
class SparseIndexManifest:
    index_version: str
    document_count: int
    chunk_count: int
    token_count: int
    active: bool = False
    built_at: str = ""


class PersistentSparseIndex:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.versions = self.root / "versions"
        self.active_pointer = self.root / "ACTIVE"
        self.versions.mkdir(parents=True, exist_ok=True)

    def build_staging(self, chunks: list[dict[str, Any]]) -> SparseIndexManifest:
        version = datetime.now(timezone.utc).strftime("bm25-%Y%m%dT%H%M%S%fZ")
        staging = self.versions / f"{version}.staging"
        staging.mkdir(parents=True, exist_ok=False)
        active_chunks = [row for row in chunks if row.get("active", True) and not row.get("deleted", False)]
        df = Counter()
        token_count = 0
        for row in active_chunks:
            tokens = tokenize(str(row.get("content") or ""))
            token_count += len(tokens)
            df.update(set(tokens))
        (staging / "chunks.jsonl").write_text(
            "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in active_chunks) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "df.json").write_text(json.dumps(dict(df), ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        manifest = SparseIndexManifest(
            index_version=version,
            document_count=len({str(row.get("document_id")) for row in active_chunks}),
            chunk_count=len(active_chunks),
            token_count=token_count,
            built_at=datetime.now(timezone.utc).isoformat(),
        )
        (staging / "manifest.json").write_text(json.dumps(manifest.__dict__, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        return manifest

    def publish(self, index_version: str) -> SparseIndexManifest:
        staging = self.versions / f"{index_version}.staging"
        final = self.versions / index_version
        if not staging.exists():
            raise RuntimeError("SPARSE_STAGING_VERSION_NOT_FOUND")
        staging.rename(final)
        manifest = self._read_manifest(final)
        manifest = SparseIndexManifest(**{**manifest.__dict__, "active": True})
        (final / "manifest.json").write_text(json.dumps(manifest.__dict__, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        tmp = self.root / "ACTIVE.tmp"
        tmp.write_text(index_version + "\n", encoding="utf-8", newline="\n")
        tmp.replace(self.active_pointer)
        return manifest

    def load_active(self) -> tuple[BM25Retriever, SparseIndexManifest]:
        version = self.active_version()
        if not version:
            raise RuntimeError("SPARSE_ACTIVE_VERSION_NOT_FOUND")
        version_dir = self.versions / version
        chunks = [json.loads(line) for line in (version_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        manifest = self._read_manifest(version_dir)
        return BM25Retriever(chunks), manifest

    def active_version(self) -> str | None:
        if not self.active_pointer.exists():
            return None
        value = self.active_pointer.read_text(encoding="utf-8").strip()
        return value or None

    def rollback(self, index_version: str) -> SparseIndexManifest:
        target = self.versions / index_version
        if not target.exists():
            raise RuntimeError("SPARSE_ROLLBACK_VERSION_NOT_FOUND")
        tmp = self.root / "ACTIVE.tmp"
        tmp.write_text(index_version + "\n", encoding="utf-8", newline="\n")
        tmp.replace(self.active_pointer)
        return self._read_manifest(target)

    def cleanup_staging(self) -> int:
        count = 0
        for path in self.versions.glob("*.staging"):
            if path.is_dir():
                shutil.rmtree(path)
                count += 1
        return count

    @staticmethod
    def _read_manifest(version_dir: Path) -> SparseIndexManifest:
        return SparseIndexManifest(**json.loads((version_dir / "manifest.json").read_text(encoding="utf-8")))
