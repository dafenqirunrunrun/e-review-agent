from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReviewRiskAnalysis(BaseModel):
    risk_type: Literal["normal_review", "negative_review", "after_sales_risk"]
    risk_level: Literal["low", "medium", "high"]
    sentiment: Literal["positive", "neutral", "negative"]
    evidence: List[str]
    reason: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)
    need_human_review: bool
    confidence: float = Field(ge=0.0, le=1.0)
    missing_information: List[str]


class SchemaPayload(BaseModel):
    data: Dict[str, Any]


class SchemaValidationResult(BaseModel):
    valid: bool
    data: Optional[ReviewRiskAnalysis] = None
    error: Optional[str] = None


class ProviderStatus(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider_name: str
    base_url: str
    model_name: str
    api_key_env: str
    api_key_available: bool
    timeout_seconds: int
    max_retries: int
    enabled: bool
    fallback_provider: str
    current_provider: str
    fallback_active: bool
    local_model_available: bool = False
    local_model_name: Optional[str] = None
    local_model_dir: Optional[str] = None
    local_model_loaded: bool = False
    local_model_device: Optional[str] = None
    local_model_dtype: Optional[str] = None
    enable_thinking: bool = False
    dependency_available: bool = False
    load_error_summary: Optional[str] = None


class LocalQwenSmokeRequest(BaseModel):
    comment_text: str = Field(min_length=1)
    rating: int = Field(ge=1, le=5)
    image_signal: str = ""


class LocalQwenSmokeResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider: str
    model_name: str
    schema_valid: bool
    risk_level: str
    risk_type: str
    evidence: List[str]
    suggestion: str
    latency_ms: int
    fallback_used: bool
    error_summary: Optional[str] = None
