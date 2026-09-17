from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.rag.document_contract import stable_hash


DocumentFormat = Literal[
    "pdf",
    "docx",
    "pptx",
    "xlsx",
    "html",
    "markdown",
    "text",
    "csv",
    "image",
    "unknown",
]
ParserKind = Literal["lightweight", "spreadsheet_native", "pdf_text", "docling", "mineru"]
NodeType = Literal[
    "title",
    "section",
    "paragraph",
    "list_item",
    "table",
    "table_row",
    "figure",
    "caption",
    "formula",
    "code",
    "sheet",
    "slide",
]


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: float
    top: float
    right: float
    bottom: float
    coordinateSystem: Literal["top-left", "bottom-left"] = "top-left"

    @model_validator(mode="after")
    def validate_extents(self) -> "BoundingBox":
        vertical_invalid = (
            self.bottom < self.top
            if self.coordinateSystem == "top-left"
            else self.top < self.bottom
        )
        if self.right < self.left or vertical_invalid:
            raise ValueError("DOCUMENT_BBOX_INVALID")
        return self


class DocumentAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assetId: str = Field(min_length=12)
    kind: Literal["image", "chart", "page_render", "attachment"]
    mediaType: str = "application/octet-stream"
    relativePath: str = ""
    pageNumber: int | None = Field(default=None, ge=1)
    bbox: BoundingBox | None = None
    caption: str = ""
    ocrText: str = ""
    description: str = ""
    knowledgeBearing: bool = True
    contentHash: str = Field(min_length=12)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodeId: str = Field(min_length=12)
    type: NodeType
    order: int = Field(ge=0)
    text: str = ""
    parentId: str | None = None
    children: list[str] = Field(default_factory=list)
    sectionPath: list[str] = Field(default_factory=list)
    pageNumber: int | None = Field(default=None, ge=1)
    bbox: BoundingBox | None = None
    assetIds: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    sourceRef: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParserAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parser: ParserKind
    status: Literal["success", "unavailable", "failed", "skipped"]
    reasonCode: str = ""
    durationMs: float = Field(default=0.0, ge=0.0)


class DocumentProbe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: DocumentFormat
    mimeType: str = "application/octet-stream"
    sizeBytes: int = Field(default=0, ge=0)
    hasTextLayer: bool | None = None
    requiresOcr: bool = False
    imageCoverageRatio: float | None = Field(default=None, ge=0.0, le=1.0)
    tableCountHint: int = Field(default=0, ge=0)
    hasMultiColumnLayout: bool = False
    hasKnowledgeImages: bool = False


class ParserRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: ParserKind
    fallbacks: list[ParserKind] = Field(default_factory=list)
    reasonCodes: list[str] = Field(default_factory=list)
    heavy: bool = False
    requiresGpuLease: bool = False

    @property
    def chain(self) -> list[ParserKind]:
        return list(dict.fromkeys([self.primary, *self.fallbacks]))


class NormalizedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: Literal["normalized-document-v1"] = "normalized-document-v1"
    documentId: str = Field(min_length=1)
    sourceName: str = Field(min_length=1)
    sourceType: str = Field(min_length=1)
    sourceUri: str = ""
    format: DocumentFormat
    mimeType: str
    language: str = "und"
    parser: ParserKind
    parserVersion: str = "unknown"
    contentHash: str = Field(min_length=12)
    markdown: str = ""
    nodes: list[DocumentNode] = Field(default_factory=list)
    assets: list[DocumentAsset] = Field(default_factory=list)
    attempts: list[ParserAttempt] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph(self) -> "NormalizedDocument":
        node_ids = [item.nodeId for item in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("DOCUMENT_NODE_ID_DUPLICATE")
        known_nodes = set(node_ids)
        known_assets = {item.assetId for item in self.assets}
        for node in self.nodes:
            if node.parentId and node.parentId not in known_nodes:
                raise ValueError("DOCUMENT_PARENT_NODE_MISSING")
            if any(child not in known_nodes for child in node.children):
                raise ValueError("DOCUMENT_CHILD_NODE_MISSING")
            if any(asset not in known_assets for asset in node.assetIds):
                raise ValueError("DOCUMENT_ASSET_MISSING")
        return self

    @classmethod
    def content_digest(cls, *, markdown: str, nodes: list[DocumentNode], assets: list[DocumentAsset]) -> str:
        return stable_hash(
            {
                "markdown": markdown,
                "nodes": [item.model_dump(mode="json") for item in nodes],
                "assets": [item.model_dump(mode="json") for item in assets],
            }
        )
