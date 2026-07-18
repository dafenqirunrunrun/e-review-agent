from fastapi import APIRouter

from app.agent_framework.graph import run_agent_graph
from app.core.config import settings
from app.schemas.review import ReviewAnalyzeRequest, ReviewAnalyzeResponse
from app.services.mock_analyzer import MockAnalyzer
from app.services.rule_agent import RuleAgentWorkflow
from app.llm.service import LlmReviewService


router = APIRouter(prefix="/review", tags=["review"])

analyzer = MockAnalyzer()
workflow = RuleAgentWorkflow(analyzer=analyzer)
llm_service = LlmReviewService(workflow)


@router.post("/analyze", response_model=ReviewAnalyzeResponse)
def analyze_review(payload: ReviewAnalyzeRequest) -> ReviewAnalyzeResponse:
    if settings.agent_framework_enabled:
        return llm_service.enhance(payload, run_agent_graph(payload, analyzer))
    return llm_service.analyze(payload)
