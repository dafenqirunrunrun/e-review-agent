from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


TrustLevel = Literal["internal_verified", "internal_unverified", "synthetic", "external_untrusted"]


def stable_hash(value: str | bytes | dict[str, Any]) -> str:
    if isinstance(value, dict):
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    elif isinstance(value, str):
        payload = value.encode("utf-8", errors="replace")
    else:
        payload = value
    return hashlib.sha256(payload).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DocumentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    document_version: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_uri_hash: str = Field(min_length=12)
    title: str = Field(min_length=1)
    content_hash: str = Field(min_length=12)
    created_at: str
    updated_at: str
    trust_level: TrustLevel = "internal_unverified"
    access_scope: str = "tenant"
    language: str = "zh"
    metadata: dict[str, Any] = Field(default_factory=dict)
    deleted: bool = False
    supersedes_version: str | None = None

    @classmethod
    def from_text(
        cls,
        *,
        tenant_id: str,
        document_id: str,
        document_version: str,
        source_type: str,
        source_uri: str,
        title: str,
        content: str,
        trust_level: TrustLevel = "internal_unverified",
        metadata: dict[str, Any] | None = None,
    ) -> "DocumentRecord":
        timestamp = now_iso()
        return cls(
            tenant_id=tenant_id,
            document_id=document_id,
            document_version=document_version,
            source_type=source_type,
            source_uri_hash=stable_hash(source_uri),
            title=title,
            content_hash=stable_hash(content),
            created_at=timestamp,
            updated_at=timestamp,
            trust_level=trust_level,
            metadata=metadata or {},
        )


class ChunkRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=12)
    document_id: str = Field(min_length=1)
    document_version: str = Field(min_length=1)
    parent_chunk_id: str | None = None
    chunk_index: int = Field(ge=0)
    content_hash: str = Field(min_length=12)
    token_count: int = Field(ge=0)
    embedding_version: str = "hash-v1"
    metadata: dict[str, Any] = Field(default_factory=dict)
    trust_level: TrustLevel = "internal_unverified"
    active: bool = True

    @classmethod
    def from_content(
        cls,
        *,
        document_id: str,
        document_version: str,
        chunk_index: int,
        content: str,
        token_count: int,
        parent_chunk_id: str | None = None,
        trust_level: TrustLevel = "internal_unverified",
        metadata: dict[str, Any] | None = None,
    ) -> "ChunkRecord":
        content_hash = stable_hash(content)
        chunk_key = f"{document_id}:{document_version}:{chunk_index}:{content_hash}"
        return cls(
            chunk_id=stable_hash(chunk_key)[:24],
            document_id=document_id,
            document_version=document_version,
            parent_chunk_id=parent_chunk_id,
            chunk_index=chunk_index,
            content_hash=content_hash,
            token_count=token_count,
            trust_level=trust_level,
            metadata=metadata or {},
        )
