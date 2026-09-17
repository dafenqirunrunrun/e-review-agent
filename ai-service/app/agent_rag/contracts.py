from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SCHEMA_VERSION = "2.0.0"
ANALYZER_VERSION = "agent-rag-phase1-v1"
PUBLIC_TENANT = "__public__"

RuntimeMode = Literal["local-model", "model-only", "rule-fallback", "explicit-failure"]
SubjectType = Literal["review", "risk_task", "operation_case"]
RiskLevel = Literal["low", "medium", "high"]
Action = Literal["none", "create-risk-task", "manual-review", "explicit-failure"]


class RetrievalOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    topK: int = Field(default=8, ge=1, le=20)
    rerankTopK: int = Field(default=4, ge=1, le=20)
    minScore: float = Field(default=0.0, ge=0.0)
    requestedMode: str = "bm25-first-semantic-hybrid"
    publicTenantEnabled: bool = True


class AgentRagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requestId: str = Field(min_length=1)
    tenantId: str = Field(min_length=1)
    subjectType: SubjectType = "review"
    subjectId: str = Field(min_length=1)
    query: str = Field(min_length=1, max_length=4096)
    context: dict[str, Any] = Field(default_factory=dict)
    runtimeMode: RuntimeMode = "local-model"
    retrieval: RetrievalOptions = Field(default_factory=RetrievalOptions)
    schemaVersion: str = SCHEMA_VERSION

    @field_validator("schemaVersion")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError("SCHEMA_VERSION_UNSUPPORTED")
        return value


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documentId: str = Field(min_length=1)
    chunkId: str = Field(min_length=1)
    tenantId: str = Field(min_length=1)
    sourceType: str = Field(min_length=1)
    title: str = Field(min_length=1)
    score: float
    rank: int = Field(ge=1)
    contentHash: str = Field(min_length=12)
    snippet: str = Field(default="", max_length=240)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    riskLevel: RiskLevel
    riskTypes: list[str] = Field(default_factory=list)
    action: Action


class Analysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=800)
    confidence: float = Field(ge=0.0, le=1.0)


class RetrievalTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    used: bool
    query: str
    originalQuery: str
    normalizedQuery: str
    topK: int
    returned: int
    rerankerType: str
    requestedRerankerType: str = ""
    effectiveRerankerType: str = ""
    rerankerModelId: str = ""
    rerankerRevision: str = ""
    rerankerModelName: str = ""
    rerankerFingerprint: str = ""
    rerankerInputCount: int = 0
    rerankerOutputCount: int = 0
    rerankerDurationMs: int = 0
    rerankerFallbackUsed: bool = False
    rerankerFallbackReason: str = ""
    indexVersion: str
    embeddingModel: str
    embeddingDimension: int
    candidateCount: int
    citations: list[Citation] = Field(default_factory=list)
    retrievalEmpty: bool = False
    denseProvider: str = ""
    requestedProviderImpl: str = ""
    effectiveProviderImpl: str = ""
    providerConformance: str = ""
    providerLibrary: str = ""
    providerLibraryVersion: str = ""
    assetFingerprint: str = ""
    providerFingerprint: str = ""
    effectiveEmbeddingFingerprint: str = ""
    indexProviderImpl: str = ""
    indexEffectiveEmbeddingFingerprint: str = ""
    providerIndexCompatible: bool = False
    requestedRetrievalMode: str = ""
    effectiveRetrievalMode: str = ""
    modelName: str = ""
    modelFingerprint: str = ""
    device: str = ""
    faissIndexType: str = ""
    faissMetric: str = ""
    embeddingDurationMs: int = 0
    faissSearchDurationMs: int = 0
    denseFallbackUsed: bool = False
    denseFallbackReason: str = ""
    targetMode: str = ""


class RuntimeTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engineType: str
    modelName: str = ""
    fallbackUsed: bool
    fallbackReason: str = ""
    analyzerVersion: str = ANALYZER_VERSION
    schemaVersion: str = SCHEMA_VERSION
    modelOutputValid: bool
    repairAttemptCount: int = 0
    validationErrors: list[str] = Field(default_factory=list)
    targetMode: str = ""
    securityGovernanceStatus: str = "pass"
    piiRedactionCount: int = 0
    promptInjectionDetected: bool = False
    promptInjectionAction: str = "none"
    requestedLlmProvider: str = "deterministic"
    effectiveLlmProvider: str = "deterministic"
    requestedAnalysisProvider: str = "deterministic"
    effectiveAnalysisProvider: str = "deterministic"
    llmModelId: str = ""
    llmRevision: str = ""
    llmFingerprint: str = ""
    promptVersion: str = ""
    promptFingerprint: str = ""
    llmInputTokens: int = 0
    llmOutputTokens: int = 0
    llmDurationMs: int = 0
    structuredOutputValid: bool = False
    groundingStatus: str = ""
    abstained: bool = False
    uncertaintyReason: str = ""
    requiresHumanReview: bool = False
    llmFallbackUsed: bool = False
    llmGrounded: bool = False
    llmFallbackReason: str = ""


class AgentTraceStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodeName: str
    startedAt: str
    finishedAt: str
    status: str
    inputHash: str
    outputHash: str
    errorCode: str = ""


class AuditTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    startedAt: str
    finishedAt: str
    durationMs: int
    agentPath: list[AgentTraceStep]
    evidenceId: str


class AgentRagResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requestId: str
    tenantId: str
    subjectId: str
    decision: Decision
    analysis: Analysis
    retrieval: RetrievalTrace
    runtime: RuntimeTrace
    audit: AuditTrace


class AgentRagEvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidenceId: str
    requestId: str
    tenantId: str
    subjectId: str
    sourceCommit: str
    runtimeMode: RuntimeMode
    schemaVersion: str
    analyzerVersion: str
    indexVersion: str
    retrievalEvidence: list[Citation]
    agentTrace: list[AgentTraceStep]
    decision: dict[str, Any]
    timing: dict[str, Any]
    errors: list[str] = Field(default_factory=list)
    denseProvider: str = ""
    requestedProviderImpl: str = ""
    effectiveProviderImpl: str = ""
    providerConformance: str = ""
    providerLibrary: str = ""
    providerLibraryVersion: str = ""
    assetFingerprint: str = ""
    providerFingerprint: str = ""
    effectiveEmbeddingFingerprint: str = ""
    indexProviderImpl: str = ""
    indexEffectiveEmbeddingFingerprint: str = ""
    providerIndexCompatible: bool = False
    requestedRetrievalMode: str = ""
    effectiveRetrievalMode: str = ""
    modelName: str = ""
    modelFingerprint: str = ""
    embeddingDimension: int = 0
    device: str = ""
    faissIndexType: str = ""
    faissMetric: str = ""
    embeddingDurationMs: int = 0
    faissSearchDurationMs: int = 0
    denseFallbackUsed: bool = False
    denseFallbackReason: str = ""
    targetMode: str = ""
    requestedRerankerType: str = ""
    effectiveRerankerType: str = ""
    rerankerModelId: str = ""
    rerankerRevision: str = ""
    rerankerModelName: str = ""
    rerankerFingerprint: str = ""
    rerankerInputCount: int = 0
    rerankerOutputCount: int = 0
    rerankerDurationMs: int = 0
    rerankerFallbackUsed: bool = False
    rerankerFallbackReason: str = ""
    securityGovernanceStatus: str = "pass"
    piiRedactionCount: int = 0
    promptInjectionDetected: bool = False
    promptInjectionAction: str = "none"
    inputContentHash: str = ""
    sanitizedContentHash: str = ""
    requestedLlmProvider: str = "deterministic"
    effectiveLlmProvider: str = "deterministic"
    requestedAnalysisProvider: str = "deterministic"
    effectiveAnalysisProvider: str = "deterministic"
    llmModelId: str = ""
    llmRevision: str = ""
    llmFingerprint: str = ""
    promptVersion: str = ""
    promptFingerprint: str = ""
    llmInputTokens: int = 0
    llmOutputTokens: int = 0
    llmDurationMs: int = 0
    structuredOutputValid: bool = False
    groundingStatus: str = ""
    abstained: bool = False
    uncertaintyReason: str = ""
    requiresHumanReview: bool = False
    llmFallbackUsed: bool = False
    llmGrounded: bool = False
    llmFallbackReason: str = ""
    llmOutputHash: str = ""
    evidenceEligibilityVersion: str = ""
    evidenceEvaluationTimeUtc: str = ""
    preRerankerCandidateCount: int = 0
    eligibleCandidateCount: int = 0
    ineligibleCandidateCount: int = 0
    expiredRejectedCount: int = 0
    inactiveRejectedCount: int = 0
    tenantRejectedCount: int = 0
    notYetEffectiveRejectedCount: int = 0
    answerabilityPolicyVersion: str = ""
    answerabilityPolicyType: str = ""
    answerabilityDecision: str = ""
    answerabilityScore: float = 0.0
    maximumFinalK: int = 5
    acceptedEvidenceCount: int = 0
    rejectedEvidenceCount: int = 0
    lowScoreBackfillCount: int = 0
    analysisInvocationDecision: str = ""
