from fastapi import APIRouter

from app.agent_framework import config
from app.agent_framework.graph import run_agent_graph
from app.schemas.review import AgentFrameworkStatus, ReviewAnalyzeRequest, ReviewAnalyzeResponse
from app.services.mock_analyzer import MockAnalyzer


router = APIRouter(prefix="/agent-framework", tags=["agent-framework"])
analyzer = MockAnalyzer()


@router.get("/status", response_model=AgentFrameworkStatus)
def framework_status() -> AgentFrameworkStatus:
    return AgentFrameworkStatus(**config.status())


@router.post("/analyze", response_model=ReviewAnalyzeResponse)
def framework_analyze(payload: ReviewAnalyzeRequest) -> ReviewAnalyzeResponse:
    return run_agent_graph(payload, analyzer, force_framework=True)
