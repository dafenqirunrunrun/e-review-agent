from fastapi import APIRouter

from app.agentic_workflow.workflow import AgenticReviewWorkflow
from app.agent_framework.graph import run_agent_graph
from app.contracts.review_governance import attach_review_governance
from app.core.config import settings
from app.schemas.review import ReviewAnalyzeRequest, ReviewAnalyzeResponse
from app.services.mock_analyzer import MockAnalyzer
from app.services.rule_agent import RuleAgentWorkflow
from app.llm.service import LlmReviewService
from app.observability.fast_eligibility_shadow import observe_fast_eligibility_shadow


router = APIRouter(prefix="/review", tags=["review"])

analyzer = MockAnalyzer()
workflow = RuleAgentWorkflow(analyzer=analyzer)
llm_service = LlmReviewService(workflow)
agentic_workflow = AgenticReviewWorkflow(analyzer=analyzer)


@router.post("/analyze", response_model=ReviewAnalyzeResponse)
def analyze_review(payload: ReviewAnalyzeRequest) -> ReviewAnalyzeResponse:
    if settings.agentic_workflow_enabled:
        response = agentic_workflow.analyze(payload)
        fast_runtime = (response.extra or {}).get("fastEligibilityRuntime", {})
        input_gate = (response.extra or {}).get("inputGate", {})
        if not fast_runtime.get("skipModelEnhancement", False) and not input_gate.get("skipModelEnhancement", False):
            response = llm_service.enhance(payload, response)
    elif settings.agent_framework_enabled:
        response = llm_service.enhance(payload, run_agent_graph(payload, analyzer))
    else:
        response = llm_service.analyze(payload)
    response = attach_review_governance(payload, response)
    try:
        observe_fast_eligibility_shadow(payload, response)
    except Exception:
        # Shadow observation is never allowed to change the business response.
        pass
    return response


@router.post("/shadow-audit", response_model=ReviewAnalyzeResponse)
def shadow_audit(payload: ReviewAnalyzeRequest) -> ReviewAnalyzeResponse:
    """Strict, non-persisted sample used only to observe light-path router disagreement."""
    payload.audit_mode = "shadow_strict"
    if settings.agentic_workflow_enabled:
        return attach_review_governance(payload, llm_service.enhance(payload, agentic_workflow.analyze(payload)))
    return analyze_review(payload)
