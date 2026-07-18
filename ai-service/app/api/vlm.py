from fastapi import APIRouter, HTTPException

from app.vlm.schemas import (
    ImageAnalyzeRequest,
    TextImageConsistencyRequest,
    VisualEvidenceResult,
    VlmSmokeResponse,
    VlmStatus,
)
from app.vlm.service import vlm_service


router = APIRouter(prefix="/vlm", tags=["vlm"])


@router.get("/status", response_model=VlmStatus)
def status() -> VlmStatus:
    return vlm_service().status()


@router.post("/image/analyze", response_model=VisualEvidenceResult)
def analyze(payload: ImageAnalyzeRequest) -> VisualEvidenceResult:
    try:
        return vlm_service().analyze(payload.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/text-image/consistency")
def consistency(payload: TextImageConsistencyRequest):
    return vlm_service().consistency(payload)


@router.post("/schema/validate")
def validate_schema(payload: dict):
    return vlm_service().validate_schema(payload)


@router.post("/smoke-test", response_model=VlmSmokeResponse)
def smoke_test() -> VlmSmokeResponse:
    return vlm_service().smoke_test()
