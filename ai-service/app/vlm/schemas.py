from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ImageQuality = Literal["clear", "blurred", "occluded", "irrelevant", "uncertain"]
FindingType = Literal[
    "package_damage", "product_damage", "leakage", "missing_part", "product_mismatch",
    "contamination", "irrelevant", "other",
]
Consistency = Literal["consistent", "conflicting", "unrelated", "uncertain"]
VisualRiskLevel = Literal["low", "medium", "high", "uncertain"]


class VisualFinding(BaseModel):
    type: FindingType
    description: str
    confidence: float = Field(ge=0.0, le=1.0)


class VisualEvidenceResult(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    image_available: bool
    image_quality: ImageQuality
    ocr_text: List[str] = Field(default_factory=list)
    visual_findings: List[VisualFinding] = Field(default_factory=list)
    package_damage_detected: bool = False
    product_damage_detected: bool = False
    leakage_detected: bool = False
    missing_part_detected: bool = False
    product_mismatch_detected: bool = False
    privacy_risk_detected: bool = False
    text_image_consistency: Consistency = "uncertain"
    visual_risk_level: VisualRiskLevel = "uncertain"
    visual_evidence: List[str] = Field(default_factory=list)
    unsupported_visual_claims: List[str] = Field(default_factory=list)
    need_human_review: bool = True
    missing_information: List[str] = Field(default_factory=list)
    provider_name: Optional[str] = None
    model_name: Optional[str] = None
    real_inference: Optional[bool] = None
    cuda_used: Optional[bool] = None
    fallback_used: Optional[bool] = None
    generate_executed: Optional[bool] = None
    schema_valid: Optional[bool] = None
    raw_schema_valid: Optional[bool] = None
    repair_used: Optional[bool] = None
    repaired_schema_valid: Optional[bool] = None
    repair_reason: Optional[str] = None
    raw_schema_failure_reasons: Optional[List[str]] = None
    deterministic_normalization_used: Optional[bool] = None
    deterministic_normalization_success: Optional[bool] = None
    safe_repair_used: Optional[bool] = None
    safe_repair_success: Optional[bool] = None
    second_generate_count: Optional[int] = None
    parse_ms: Optional[float] = None
    normalization_ms: Optional[float] = None
    repair_ms: Optional[float] = None
    latency_ms: Optional[float] = None
    model_load_ms: Optional[float] = None
    inference_ms: Optional[float] = None
    gpu_peak_memory_mb: Optional[float] = None
    gpu_memory_after_unload_mb: Optional[float] = None
    input_token_count: Optional[int] = None
    output_token_count: Optional[int] = None
    latency_breakdown: Optional[dict] = None
    runtime_counters: Optional[dict] = None


class VlmStatus(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider: str
    model_name: str
    model_dir: str
    model_available: bool
    device: str
    dtype: str
    load_in_4bit: bool
    max_images: int
    max_pixels: int
    min_pixels: int = 65_536
    lazy_load: bool = True
    unload_after_request: bool = True
    memory_strategy: str
    loaded: bool
    blocked_reason: Optional[str] = None


class ImageAnalyzeRequest(BaseModel):
    image_paths: List[str] = Field(default_factory=list)
    image_urls: List[str] = Field(default_factory=list)
    review_text: str = ""
    product_name: str = ""


class TextImageConsistencyRequest(BaseModel):
    review_text: str
    visual_result: VisualEvidenceResult


class VlmSmokeResponse(BaseModel):
    marker: str
    status: VlmStatus
    schema_valid: bool
    message: str
