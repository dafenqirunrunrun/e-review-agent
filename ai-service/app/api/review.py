from fastapi import APIRouter, Request

from app.agent_framework.graph import run_agent_graph
from app.core.config import settings
from app.schemas.review import ReviewAnalyzeRequest, ReviewAnalyzeResponse
from app.services.mock_analyzer import MockAnalyzer
from app.services.rule_agent import RuleAgentWorkflow
from app.llm.service import LlmReviewService
from app.observability import record_ai_analysis


router = APIRouter(prefix="/review", tags=["review"])

analyzer = MockAnalyzer()
workflow = RuleAgentWorkflow(analyzer=analyzer)
llm_service = LlmReviewService(workflow)


@router.post("/analyze", response_model=ReviewAnalyzeResponse)
def analyze_review(payload: ReviewAnalyzeRequest, request: Request) -> ReviewAnalyzeResponse:
    request_id = getattr(request.state, "request_id", "")
    try:
        if settings.agent_framework_enabled:
            response = llm_service.enhance(payload, run_agent_graph(payload, analyzer))
        else:
            response = llm_service.analyze(payload)
        record_ai_analysis(request_id, True)
        return response
    except Exception:
        record_ai_analysis(request_id, False)
        raise
