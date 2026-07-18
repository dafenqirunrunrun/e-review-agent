from fastapi import APIRouter, HTTPException

from app.llm.schemas import LocalQwenSmokeRequest, LocalQwenSmokeResponse, ProviderStatus, SchemaPayload, SchemaValidationResult
from app.llm.service import LlmReviewService
from app.schemas.review import ReviewAnalyzeRequest, ReviewAnalyzeResponse
from app.services.mock_analyzer import MockAnalyzer
from app.services.rule_agent import RuleAgentWorkflow


router = APIRouter(prefix="/llm", tags=["llm"])
service = LlmReviewService(RuleAgentWorkflow(MockAnalyzer()))


@router.post("/review/analyze", response_model=ReviewAnalyzeResponse)
def analyze_review(payload: ReviewAnalyzeRequest) -> ReviewAnalyzeResponse:
    return service.analyze(payload)


@router.get("/provider/status", response_model=ProviderStatus)
def provider_status() -> ProviderStatus:
    return service.provider_status()


@router.post("/schema/validate", response_model=SchemaValidationResult)
def validate_schema(payload: SchemaPayload) -> SchemaValidationResult:
    return service.validate_data(payload.data)


@router.post("/schema/repair", response_model=SchemaValidationResult)
def repair_schema(payload: SchemaPayload) -> SchemaValidationResult:
    result = service.repair_data(payload.data)
    if not result.valid:
        raise HTTPException(status_code=422, detail=result.error)
    return result


@router.post("/local-qwen/smoke-test", response_model=LocalQwenSmokeResponse)
def local_qwen_smoke_test(payload: LocalQwenSmokeRequest) -> LocalQwenSmokeResponse:
    response = service.analyze(ReviewAnalyzeRequest(
        review_id="local-qwen-smoke",
        product_id="LOCAL-QWEN-SMOKE",
        product_name="本地 Qwen3 冒烟测试商品",
        review_text=payload.comment_text,
        image_urls=[payload.image_signal] if payload.image_signal else [],
        rating=payload.rating,
    ))
    extra = response.extra or {}
    suggestion = response.agent_suggestion
    return LocalQwenSmokeResponse(
        provider=response.llm_provider or "local_rule_fallback",
        model_name=response.model_name or "",
        schema_valid=bool(response.schema_valid),
        risk_level=response.risk_level,
        risk_type=str(extra.get("risk_type") or "unknown"),
        evidence=response.evidence,
        suggestion=suggestion.operation_advice,
        latency_ms=response.latency_ms or 0,
        fallback_used=response.fallback_used,
        error_summary=response.schema_error,
    )
