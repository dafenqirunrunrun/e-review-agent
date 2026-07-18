from app.schemas.review import ReviewAnalyzeRequest, ReviewAnalyzeResponse
from app.services.rule_agent import RuleAgentWorkflow
from app.services.base import AnalyzerBase


def run_legacy_fallback(payload: ReviewAnalyzeRequest, analyzer: AnalyzerBase) -> ReviewAnalyzeResponse:
    response = RuleAgentWorkflow(analyzer=analyzer).run(payload)
    response.framework = "legacy_rule_agent"
    response.fallback_used = True
    response.extra = {"fallback_reason": "agent framework unavailable or failed"}
    for item in response.workflow_trace:
        item.framework = "legacy_rule_agent"
    return response
