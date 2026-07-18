from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from app.rag_v2.schemas import (
    RagEvaluateRequest,
    RagEvaluateResponse,
    RagSearchRequest,
    RagSearchResponse,
    RagStatus,
)
from app.rag_v2.service import rag_v2_service


router = APIRouter(prefix="/rag-v2", tags=["rag-v2"])
REPORT = Path(__file__).resolve().parents[3] / "docs" / "103_v16_hybrid_rag_eval_report.md"


@router.get("/status", response_model=RagStatus)
def status() -> RagStatus:
    return RagStatus.model_validate(rag_v2_service().status())


@router.post("/index/build")
def build_index():
    try:
        return {"marker": "RAG_INDEX_BUILD_PASS", "metadata": rag_v2_service().build_index()}
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)[:200]) from exc


@router.post("/search", response_model=RagSearchResponse)
def search(payload: RagSearchRequest) -> RagSearchResponse:
    return RagSearchResponse.model_validate(rag_v2_service().search(payload.model_dump()))


@router.post("/evaluate", response_model=RagEvaluateResponse)
def evaluate(payload: RagEvaluateRequest) -> RagEvaluateResponse:
    return RagEvaluateResponse.model_validate(rag_v2_service().evaluate(payload.strategies))


@router.get("/report", response_class=PlainTextResponse)
def report() -> str:
    if not REPORT.exists():
        raise HTTPException(status_code=404, detail="RAG_EVAL_REPORT_NOT_AVAILABLE")
    return REPORT.read_text(encoding="utf-8")
