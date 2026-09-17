from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


AnnotationStatus = Literal[
    "pending_human_review",
    "human_verified",
    "llm_adjudicated",
    "rejected",
]


class QualityQrel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunkId: str = Field(min_length=1)
    relevance: int = Field(ge=0, le=3)
    supports: list[str] = Field(default_factory=list)
    sourceName: str = ""
    sourceType: str = ""
    sourceLevel: str = ""
    clauseId: str = ""
    rationale: str = ""


class RagQualityCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: Literal["rag-quality-case-v2"] = "rag-quality-case-v2"
    datasetVersion: str
    caseId: str
    split: Literal["dev", "holdout"]
    smoke: bool = False
    language: Literal["zh"] = "zh"
    reviewText: str = Field(min_length=1)
    queryStyle: str
    riskTypes: list[str] = Field(default_factory=list)
    riskLevel: Literal["normal", "low", "medium", "high"]
    noAnswer: bool = False
    sourceLanguage: Literal["zh", "en", "mixed", "not_applicable"] = "mixed"
    documentFormat: str = "html"
    qrels: list[QualityQrel] = Field(default_factory=list)
    qrelCompleteness: Literal["pooled_partial", "draft_pool", "complete"]
    annotationStatus: AnnotationStatus
    annotationSource: str
    candidateExposure: bool = False
    requiresAdjudication: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_case(self) -> "RagQualityCase":
        chunk_ids = [item.chunkId for item in self.qrels]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("RAG_QUALITY_QREL_DUPLICATE")
        if self.noAnswer and any(item.relevance >= 2 for item in self.qrels):
            raise ValueError("RAG_QUALITY_NO_ANSWER_HAS_SUPPORT")
        if self.riskLevel == "normal" and self.riskTypes:
            raise ValueError("RAG_QUALITY_NORMAL_CASE_HAS_RISK")
        if self.annotationStatus in {"human_verified", "llm_adjudicated"} and self.requiresAdjudication:
            raise ValueError("RAG_QUALITY_VERIFIED_CASE_STILL_REQUIRES_ADJUDICATION")
        return self


class RetrievalHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunkId: str
    score: float
    sourceName: str = ""
    sourceUrl: str = ""
    sectionPath: list[str] = Field(default_factory=list)
    clauseId: str = ""
    contentHash: str = ""


class RetrievalRunCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caseId: str
    abstained: bool = False
    hits: list[RetrievalHit] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParserFixtureExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixtureId: str
    expectedFormat: str
    requiredAnchors: list[str] = Field(default_factory=list)
    orderedAnchors: list[str] = Field(default_factory=list)
    requiredNodeTypes: list[str] = Field(default_factory=list)
    requiredSectionPaths: list[str] = Field(default_factory=list)
    requiredTableCells: list[str] = Field(default_factory=list)
    requiredRouteReasons: list[str] = Field(default_factory=list)
    minimumNodeCount: int = Field(default=1, ge=0)
    minimumReferencedPageCount: int = Field(default=0, ge=0)
    minimumAssetCount: int = Field(default=0, ge=0)
    requireAssetAssociation: bool = False
