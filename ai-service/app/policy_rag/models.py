from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.rag.document_contract import stable_hash


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


ParserName = Literal[
    "mineru",
    "docling",
    "pypdf_text",
    "spreadsheet_native",
    "lightweight_html",
    "manual_markdown",
    "plain_text",
]
LicenseClass = Literal["public_domain", "public_reference_restricted", "project_owned"]


class PolicySourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sourceId: str = Field(min_length=1)
    sourceUrl: str = Field(min_length=1)
    sourceName: str = Field(min_length=1)
    sourceType: str = Field(min_length=1)
    jurisdiction: str = "platform"
    language: str = "en"
    parser: ParserName = "manual_markdown"
    parserVersion: str = "policy-rag-v1"
    licenseClass: LicenseClass = "public_reference_restricted"
    fetchedAt: str = Field(default_factory=utc_now)
    contentHash: str = Field(min_length=12)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_content(cls, *, content: str, **kwargs: Any) -> "PolicySourceManifest":
        kwargs.setdefault("contentHash", stable_hash(content))
        return cls(**kwargs)


class ParsedPolicyDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: PolicySourceManifest
    markdown: str = Field(min_length=1)
    structured: dict[str, Any] = Field(default_factory=dict)
    parserWarnings: list[str] = Field(default_factory=list)


class PolicyChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunkId: str = Field(min_length=12)
    documentId: str = Field(min_length=1)
    sourceName: str = Field(min_length=1)
    sourceUrl: str = Field(min_length=1)
    sourceType: str = Field(min_length=1)
    jurisdiction: str = "platform"
    licenseClass: LicenseClass = "public_reference_restricted"
    language: str = "en"
    heading: str = ""
    sectionPath: list[str] = Field(default_factory=list)
    clauseId: str = ""
    pageNumber: int | None = None
    text: str = Field(min_length=1)
    parentChunkId: str | None = None
    riskTypes: list[str] = Field(default_factory=list)
    evidenceTags: list[str] = Field(default_factory=list)
    effectiveFrom: str = "1970-01-01T00:00:00Z"
    contentHash: str = Field(min_length=12)
    tokenCount: int = Field(ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def as_retriever_row(self) -> dict[str, Any]:
        return {
            "tenant_id": "__public__",
            "document_id": self.documentId,
            "document_version": self.effectiveFrom,
            "chunk_id": self.chunkId,
            "content": self.text,
            "text": self.text,
            "content_hash": self.contentHash,
            "source_type": self.sourceType,
            "title": self.heading or self.sourceName,
            "active": True,
            "deleted": False,
            "visibility": "public",
            "effective_from": self.effectiveFrom,
            "metadata": {
                **self.metadata,
                "sourceName": self.sourceName,
                "sourceUrl": self.sourceUrl,
                "sectionPath": self.sectionPath,
                "clauseId": self.clauseId,
                "riskTypes": self.riskTypes,
                "evidenceTags": self.evidenceTags,
                "licenseClass": self.licenseClass,
                "jurisdiction": self.jurisdiction,
                "language": self.language,
            },
        }


class PolicySearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidenceId: str
    chunkId: str = ""
    sourceType: str
    sourceName: str
    sourceUrl: str
    title: str
    snippet: str
    riskTypes: list[str]
    evidenceTags: list[str]
    score: float
    contentHash: str
    sectionPath: list[str] = Field(default_factory=list)
    clauseId: str = ""
    licenseClass: str = ""
    retrievalMode: str = "bm25_metadata_fallback"
    retrieval: dict[str, Any] = Field(default_factory=dict)


class ReflectionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    evidenceStatus: Literal["supported", "insufficient", "mismatch"] = "insufficient"
    reasonCodes: list[str] = Field(default_factory=list)
    summary: str
    technicalSummary: str = ""
    primaryReasonCode: str = ""
    failureReasons: list[dict[str, Any]] = Field(default_factory=list)
    riskCoverage: list[dict[str, Any]] = Field(default_factory=list)
    supportedRiskTypes: list[str] = Field(default_factory=list)
    unsupportedRiskTypes: list[str] = Field(default_factory=list)
    citationValidationErrors: list[str] = Field(default_factory=list)
    requiresHumanReview: bool = False
    replanHints: dict[str, Any] = Field(default_factory=dict)
