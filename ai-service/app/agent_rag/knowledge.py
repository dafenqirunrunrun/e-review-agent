from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.rag.document_contract import stable_hash
from app.rag.tenant_acl import normalize_tenant_id


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SourceType(str, Enum):
    policy = "policy"
    product_manual = "product-manual"
    platform_rule = "platform-rule"
    risk_case = "risk-case"
    faq = "faq"
    customer_service = "customer-service"
    public_regulation = "public-regulation"
    internal_guideline = "internal-guideline"


class KnowledgeStatus(str, Enum):
    active = "active"
    retired = "retired"
    disabled = "disabled"
    deleted = "deleted"


class IndexStatus(str, Enum):
    building = "building"
    ready = "ready"
    active = "active"
    failed = "failed"
    retired = "retired"


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documentId: str = Field(min_length=1)
    tenantId: str = Field(min_length=1)
    sourceType: SourceType
    sourceUri: str = ""
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    language: str = "zh-CN"
    effectiveFrom: str = "1970-01-01T00:00:00Z"
    effectiveTo: str | None = None
    status: KnowledgeStatus = KnowledgeStatus.active
    version: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    contentHash: str = Field(min_length=12)
    createdAt: str = Field(default_factory=utc_now)
    updatedAt: str = Field(default_factory=utc_now)
    visibility: str = "tenant"

    @field_validator("tenantId")
    @classmethod
    def _tenant_safe(cls, value: str) -> str:
        if value == "__public__":
            return value
        return normalize_tenant_id(value)

    @field_validator("visibility")
    @classmethod
    def _visibility_supported(cls, value: str) -> str:
        if value not in {"tenant", "public"}:
            raise ValueError("KNOWLEDGE_VISIBILITY_UNSUPPORTED")
        return value

    @classmethod
    def from_text(cls, **kwargs: Any) -> "KnowledgeDocument":
        content = str(kwargs["content"])
        kwargs.setdefault("contentHash", stable_hash(content))
        return cls(**kwargs)


class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunkId: str = Field(min_length=1)
    documentId: str = Field(min_length=1)
    tenantId: str = Field(min_length=1)
    chunkIndex: int = Field(ge=0)
    text: str = Field(min_length=1)
    tokenCount: int = Field(ge=1)
    contentHash: str = Field(min_length=12)
    sectionTitle: str = ""
    sourceType: SourceType
    documentVersion: str = Field(min_length=1)
    effectiveFrom: str = "1970-01-01T00:00:00Z"
    effectiveTo: str | None = None
    status: KnowledgeStatus = KnowledgeStatus.active
    metadata: dict[str, Any] = Field(default_factory=dict)
    title: str = ""
    visibility: str = "tenant"

    def as_retriever_row(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenantId,
            "document_id": self.documentId,
            "document_version": self.documentVersion,
            "chunk_id": self.chunkId,
            "content": self.text,
            "text": self.text,
            "content_hash": self.contentHash,
            "trust_level": "internal_verified",
            "active": self.status == KnowledgeStatus.active,
            "deleted": self.status == KnowledgeStatus.deleted,
            "source_type": self.sourceType.value,
            "title": self.title or self.documentId,
            "effective_from": self.effectiveFrom,
            "effective_to": self.effectiveTo,
            "visibility": self.visibility,
            "metadata": self.metadata,
        }


class IndexManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indexVersion: str
    tenantId: str
    status: IndexStatus
    embeddingModel: str
    embeddingDimension: int
    documentCount: int
    chunkCount: int
    sparseIndexType: str = "bm25"
    denseIndexType: str = "hash-dense-fixture"
    sourceCommit: str = "local"
    configHash: str
    contentRootHash: str
    createdAt: str = Field(default_factory=utc_now)
    activatedAt: str | None = None


class IngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingestionRunId: str
    tenantId: str
    documentCount: int
    chunkCount: int
    skippedCount: int
    duplicateCount: int
    failedCount: int
    indexVersion: str
    embeddingModel: str
    embeddingDimension: int
    startedAt: str
    finishedAt: str
    manifest: IndexManifest
    errors: list[str] = Field(default_factory=list)


class KnowledgeIngestionPipeline:
    def __init__(self, *, chunk_max_tokens: int = 80, chunk_overlap_tokens: int = 8, chunk_min_chars: int = 8):
        self.chunk_max_tokens = chunk_max_tokens
        self.chunk_overlap_tokens = chunk_overlap_tokens
        self.chunk_min_chars = chunk_min_chars

    def ingest(self, documents: list[dict[str, Any] | KnowledgeDocument], *, tenant_id: str, index_version: str) -> tuple[IngestionResult, list[KnowledgeChunk]]:
        started = utc_now()
        chunks: list[KnowledgeChunk] = []
        errors: list[str] = []
        seen_content: set[str] = set()
        skipped = duplicates = failed = 0
        parsed_docs: list[KnowledgeDocument] = []
        for raw in documents:
            try:
                doc = raw if isinstance(raw, KnowledgeDocument) else KnowledgeDocument.model_validate(raw)
                if doc.tenantId not in {normalize_tenant_id(tenant_id), "__public__"}:
                    skipped += 1
                    continue
                if doc.status != KnowledgeStatus.active or not doc.content.strip():
                    skipped += 1
                    continue
                parsed_docs.append(doc)
                for chunk in self.split(doc):
                    if chunk.contentHash in seen_content:
                        duplicates += 1
                        continue
                    seen_content.add(chunk.contentHash)
                    chunks.append(chunk)
            except Exception as exc:
                failed += 1
                errors.append(str(exc))
        content_root_hash = stable_hash({"chunks": [chunk.contentHash for chunk in chunks]})
        manifest = IndexManifest(
            indexVersion=index_version,
            tenantId=normalize_tenant_id(tenant_id),
            status=IndexStatus.ready if failed == 0 else IndexStatus.failed,
            embeddingModel="hash-dense-fixture",
            embeddingDimension=64,
            documentCount=len(parsed_docs),
            chunkCount=len(chunks),
            configHash=stable_hash({"chunk_max_tokens": self.chunk_max_tokens, "chunk_overlap_tokens": self.chunk_overlap_tokens}),
            contentRootHash=content_root_hash,
        )
        return (
            IngestionResult(
                ingestionRunId=stable_hash({"tenantId": tenant_id, "indexVersion": index_version, "startedAt": started})[:24],
                tenantId=normalize_tenant_id(tenant_id),
                documentCount=len(parsed_docs),
                chunkCount=len(chunks),
                skippedCount=skipped,
                duplicateCount=duplicates,
                failedCount=failed,
                indexVersion=index_version,
                embeddingModel=manifest.embeddingModel,
                embeddingDimension=manifest.embeddingDimension,
                startedAt=started,
                finishedAt=utc_now(),
                manifest=manifest,
                errors=errors,
            ),
            chunks,
        )

    def split(self, document: KnowledgeDocument) -> list[KnowledgeChunk]:
        paragraphs = [part.strip() for part in document.content.replace("\r\n", "\n").split("\n") if part.strip()]
        output: list[KnowledgeChunk] = []
        index = 0
        for paragraph in paragraphs:
            tokens = paragraph.split()
            if len(paragraph) < self.chunk_min_chars:
                continue
            if not tokens:
                tokens = [paragraph]
            start = 0
            while start < len(tokens):
                window = tokens[start : start + self.chunk_max_tokens]
                text = " ".join(window).strip()
                if len(text) >= self.chunk_min_chars:
                    content_hash = stable_hash(text)
                    output.append(
                        KnowledgeChunk(
                            chunkId=stable_hash(f"{document.documentId}:{document.version}:{index}:{content_hash}")[:24],
                            documentId=document.documentId,
                            tenantId=document.tenantId,
                            chunkIndex=index,
                            text=text,
                            tokenCount=len(window),
                            contentHash=content_hash,
                            sectionTitle=document.title,
                            sourceType=document.sourceType,
                            documentVersion=document.version,
                            effectiveFrom=document.effectiveFrom,
                            effectiveTo=document.effectiveTo,
                            status=document.status,
                            metadata=document.metadata,
                            title=document.title,
                            visibility=document.visibility,
                        )
                    )
                    index += 1
                if len(tokens) <= self.chunk_max_tokens:
                    break
                start += max(1, self.chunk_max_tokens - self.chunk_overlap_tokens)
        return output


class LocalIndexRegistry:
    def __init__(self):
        self._indexes: dict[str, dict[str, Any]] = {}
        self._active_by_tenant: dict[str, str] = {}
        self._previous_by_tenant: dict[str, str] = {}

    def add_candidate(self, manifest: IndexManifest, chunks: list[KnowledgeChunk]) -> None:
        self._indexes[manifest.indexVersion] = {"manifest": manifest, "chunks": chunks}

    def activate_index(self, version: str) -> IndexManifest:
        entry = self._require(version)
        manifest: IndexManifest = entry["manifest"]
        if manifest.status not in {IndexStatus.ready, IndexStatus.active, IndexStatus.retired}:
            raise RuntimeError("INDEX_NOT_READY")
        current = self._active_by_tenant.get(manifest.tenantId)
        if current and current != version:
            self._previous_by_tenant[manifest.tenantId] = current
            old_entry = self._indexes[current]
            old_entry["manifest"] = old_entry["manifest"].model_copy(update={"status": IndexStatus.retired})
        activated = manifest.model_copy(update={"status": IndexStatus.active, "activatedAt": utc_now()})
        entry["manifest"] = activated
        self._active_by_tenant[manifest.tenantId] = version
        return activated

    def rollback_index(self, tenant_id: str, previous_version: str | None = None) -> IndexManifest:
        tenant = normalize_tenant_id(tenant_id)
        target = previous_version or self._previous_by_tenant.get(tenant)
        if not target:
            raise RuntimeError("INDEX_ROLLBACK_VERSION_NOT_FOUND")
        return self.activate_index(target)

    def active(self, tenant_id: str) -> tuple[IndexManifest, list[KnowledgeChunk]]:
        tenant = normalize_tenant_id(tenant_id)
        version = self._active_by_tenant.get(tenant)
        if not version:
            raise RuntimeError("ACTIVE_INDEX_NOT_FOUND")
        entry = self._require(version)
        return entry["manifest"], list(entry["chunks"])

    def _require(self, version: str) -> dict[str, Any]:
        if version not in self._indexes:
            raise RuntimeError("INDEX_VERSION_NOT_FOUND")
        return self._indexes[version]


def load_documents(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["documents"]
