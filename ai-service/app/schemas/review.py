from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class ReviewAnalyzeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    review_id: str = Field(default="", validation_alias=AliasChoices("review_id", "reviewId"))
    product_id: str = Field(..., min_length=1, coerce_numbers_to_str=True, validation_alias=AliasChoices("product_id", "productId"))
    product_name: str = Field(..., min_length=1, validation_alias=AliasChoices("product_name", "productName"))
    review_text: str = Field(..., min_length=1, validation_alias=AliasChoices("review_text", "reviewText"))
    image_urls: List[str] = Field(default_factory=list, validation_alias=AliasChoices("image_urls", "imageUrls"))
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    rating_source: Literal["USER_PROVIDED", "UNKNOWN"] = Field(
        default="UNKNOWN",
        validation_alias=AliasChoices("rating_source", "ratingSource"),
    )
    rag_enabled: Optional[bool] = Field(default=None, validation_alias=AliasChoices("rag_enabled", "ragEnabled"))
    rag_strategy: Optional[str] = Field(default=None, validation_alias=AliasChoices("rag_strategy", "ragStrategy"))
    audit_mode: Optional[str] = Field(default=None, validation_alias=AliasChoices("audit_mode", "auditMode"))

    @model_validator(mode="before")
    @classmethod
    def normalize_rating_contract(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        source_key = "rating_source" if "rating_source" in normalized else "ratingSource"
        source = normalized.get(source_key) if source_key in normalized else None
        source_explicit = source not in (None, "")
        rating = normalized.get("rating")

        # Explicit ratings from older callers remain compatible. Missing ratings
        # are never synthesized, and UNKNOWN ratings are normalized to null.
        if not source_explicit:
            normalized[source_key] = "USER_PROVIDED" if rating is not None else "UNKNOWN"
        elif source == "UNKNOWN":
            normalized["rating"] = None
        if normalized.get("rating") is None:
            normalized[source_key] = "UNKNOWN"
        return normalized


class SimilarCase(BaseModel):
    case_id: str
    review_text: str
    sentiment_label: str
    similarity: float
    label: Optional[str] = None
    reason: Optional[str] = None


class AgentSuggestion(BaseModel):
    customer_reply: str
    operation_advice: str
    after_sales_suggestion: str
    action: Optional[str] = None
    priority: Optional[str] = None
    summary: Optional[str] = None


class WorkflowTraceItem(BaseModel):
    node: str
    status: str
    message: str
    step: Optional[str] = None
    agent: Optional[str] = None
    agent_role: Optional[str] = None
    agent_goal: Optional[str] = None
    output: Optional[Any] = None
    framework: Optional[str] = None
    tool_name: Optional[str] = None
    provider: Optional[str] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class GovernanceDecision(BaseModel):
    code: str
    label: str
    riskLevel: str
    confidence: float
    needHumanReview: bool
    status: str


class GovernanceSummary(BaseModel):
    title: str
    reason: str
    explanation: str


class GovernanceRiskSignal(BaseModel):
    riskType: str
    label: str
    severity: str
    matchedText: Optional[str] = None
    reason: str
    evidenceStatus: str = "unchecked"
    supportedBy: List[str] = Field(default_factory=list)
    missingEvidenceTags: List[str] = Field(default_factory=list)


class GovernanceEvidenceCitation(BaseModel):
    id: str
    sourceName: str
    sourceType: str
    sourceLevel: str
    sourceUrl: str
    sectionPath: List[str] = Field(default_factory=list)
    clauseId: str = ""
    snippet: str
    riskTypes: List[str] = Field(default_factory=list)
    evidenceTags: List[str] = Field(default_factory=list)
    contentHash: str
    retrieval: Dict[str, Any] = Field(default_factory=dict)


class GovernanceProcessStep(BaseModel):
    order: int
    name: str
    status: str
    summary: str


class GovernanceAction(BaseModel):
    code: str
    label: str
    style: str = "default"
    requiresHuman: bool = False


class GovernanceHumanReview(BaseModel):
    required: bool
    reason: str
    trigger: Optional[str] = None
    missingInformation: List[str] = Field(default_factory=list)


class ReviewGovernanceContract(BaseModel):
    schemaVersion: str = "review-governance-v2"
    governanceSchemaVersion: str = "review-governance-v2"
    reviewId: str
    productId: str
    decision: GovernanceDecision
    summary: GovernanceSummary
    riskTypes: List[str] = Field(default_factory=list)
    evidenceStatus: str = "insufficient"
    reflectionReason: str = ""
    reflectionReasonCode: Optional[str] = None
    technicalReflectionReason: Optional[str] = None
    failureReasons: List[Dict[str, Any]] = Field(default_factory=list)
    riskCoverage: List[Dict[str, Any]] = Field(default_factory=list)
    originalGovernanceSnapshot: Optional[Dict[str, Any]] = None
    migration: Optional[Dict[str, Any]] = None
    requiresReevaluation: bool = False
    historyDisplay: Optional[Dict[str, Any]] = None
    requiresHumanReview: bool = False
    riskSignals: List[GovernanceRiskSignal] = Field(default_factory=list)
    evidenceCitations: List[GovernanceEvidenceCitation] = Field(default_factory=list)
    process: List[GovernanceProcessStep] = Field(default_factory=list)
    recommendedActions: List[GovernanceAction] = Field(default_factory=list)
    humanReview: GovernanceHumanReview


class ReviewAnalyzeResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    review_id: str
    product_id: str
    sentiment_label: str
    confidence: float
    scores: Dict[str, float]
    evidence: List[str]
    text_score: float
    image_score: float
    fusion_score: float
    conflict_score: float
    risk_level: str
    text_evidence: List[str]
    image_evidence: List[str]
    similar_cases: List[SimilarCase]
    agent_suggestion: AgentSuggestion
    workflow_trace: List[WorkflowTraceItem]
    modality_conflict: Optional[Dict] = None
    dominant_modality: Optional[Dict] = None
    framework: Optional[str] = None
    fallback_used: bool = False
    llm_provider: Optional[str] = None
    model_name: Optional[str] = None
    prompt_template: Optional[str] = None
    schema_valid: Optional[bool] = None
    schema_error: Optional[str] = None
    repair_used: bool = False
    token_usage_input: Optional[int] = None
    token_usage_output: Optional[int] = None
    latency_ms: Optional[int] = None
    need_human_review: Optional[bool] = None
    requires_human_review: Optional[bool] = None
    missing_information: List[str] = Field(default_factory=list)
    rag_enabled: bool = False
    rag_strategy: Optional[str] = None
    retrieval_hit_count: int = 0
    retrieval_top_score: float = 0.0
    retrieval_latency_ms: Optional[int] = None
    embedding_provider: Optional[str] = None
    reranker_provider: Optional[str] = None
    retrieved_case_ids: List[str] = Field(default_factory=list)
    retrieval_query_summary: Optional[str] = None
    route_decision: Optional[str] = None
    route_reason: Optional[str] = None
    evidence_sufficient: Optional[bool] = None
    evidence_status: Optional[str] = None
    reflection_reason: Optional[str] = None
    risk_types: List[str] = Field(default_factory=list)
    human_review_trigger: Optional[str] = None
    review_governance: Optional[ReviewGovernanceContract] = None
    extra: Optional[Dict] = None


class AgentFrameworkStatus(BaseModel):
    enabled: bool
    provider: str
    langgraph_available: bool
    openai_agents_available: bool
    fallback_enabled: bool
    api_key_available: bool
    current_mode: str
    last_error: Optional[str] = None
