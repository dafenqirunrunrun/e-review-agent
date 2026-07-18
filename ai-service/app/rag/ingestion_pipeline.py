from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

from app.rag.chunking import HierarchicalChunker
from app.rag.document_contract import ChunkRecord, DocumentRecord, stable_hash


ALLOWED_SUFFIXES = {".txt", ".md", ".json", ".csv", ".pdf", ".docx"}
FORBIDDEN_SUFFIXES = {".exe", ".bat", ".cmd", ".ps1", ".sh", ".js", ".vbs", ".zip", ".rar", ".7z"}


@dataclass(frozen=True)
class IngestionResult:
    status: str
    document: DocumentRecord | None = None
    chunks: list[ChunkRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False
    index_version: str | None = None


class EnterpriseIngestionPipeline:
    def __init__(self, max_bytes: int = 2_000_000, chunker: HierarchicalChunker | None = None):
        self.max_bytes = max_bytes
        self.chunker = chunker or HierarchicalChunker()
        self.published_versions: dict[str, list[ChunkRecord]] = {}

    def ingest_text(
        self,
        *,
        tenant_id: str,
        document_id: str,
        document_version: str,
        source_type: str,
        source_uri: str,
        title: str,
        content: str,
        dry_run: bool = False,
    ) -> IngestionResult:
        normalized = self._normalize_text(content)
        errors = self._scan_content(normalized)
        if errors:
            return IngestionResult(status="BLOCKED", errors=errors, dry_run=dry_run)
        document = DocumentRecord.from_text(
            tenant_id=tenant_id,
            document_id=document_id,
            document_version=document_version,
            source_type=source_type,
            source_uri=source_uri,
            title=title,
            content=normalized,
            metadata={"mime_type": "text/plain"},
        )
        chunks = [item.record for item in self.chunker.chunk(document, normalized)]
        index_version = stable_hash({"document_id": document_id, "version": document_version, "chunks": [c.chunk_id for c in chunks]})[:24]
        if not dry_run:
            self.published_versions[index_version] = chunks
        return IngestionResult(status="PASS", document=document, chunks=chunks, dry_run=dry_run, index_version=index_version)

    def validate_file(self, path: Path) -> list[str]:
        errors: list[str] = []
        resolved = path.resolve()
        if ".." in path.parts:
            errors.append("PATH_TRAVERSAL_BLOCKED")
        if resolved.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append("FORBIDDEN_FILE_TYPE")
        if resolved.suffix.lower() not in ALLOWED_SUFFIXES:
            errors.append("UNSUPPORTED_FILE_TYPE")
        if resolved.exists() and resolved.stat().st_size > self.max_bytes:
            errors.append("FILE_TOO_LARGE")
        if mimetypes.guess_type(str(resolved))[0] == "application/x-msdownload":
            errors.append("EXECUTABLE_MIME_BLOCKED")
        return errors

    def incremental_update(self, previous: DocumentRecord, content: str) -> IngestionResult:
        new_version = str(int(previous.document_version) + 1) if previous.document_version.isdigit() else f"{previous.document_version}.1"
        return self.ingest_text(
            tenant_id=previous.tenant_id,
            document_id=previous.document_id,
            document_version=new_version,
            source_type=previous.source_type,
            source_uri=previous.source_uri_hash,
            title=previous.title,
            content=content,
        )

    def full_rebuild(self) -> str:
        self.published_versions.clear()
        return "FULL_REBUILD_READY"

    def rollback_version(self, index_version: str) -> list[ChunkRecord]:
        return list(self.published_versions.get(index_version, []))

    @staticmethod
    def _normalize_text(content: str) -> str:
        return "\n".join(line.rstrip() for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n")).strip()

    @staticmethod
    def _scan_content(content: str) -> list[str]:
        lowered = content.lower()
        errors = []
        if "ignore previous instructions" in lowered or "system prompt" in lowered:
            errors.append("PROMPT_INJECTION_DETECTED")
        if "api_key=" in lowered or "bearer " in lowered:
            errors.append("SECRET_LIKE_CONTENT_DETECTED")
        return errors
