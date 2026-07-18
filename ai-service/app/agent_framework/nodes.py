from app.agent_framework.tools import (
    DominantModalityTool,
    FinalReportTool,
    ImageSignalTool,
    ModalityConflictTool,
    OperationSuggestionTool,
    RatingSignalTool,
    ReviewContextTool,
    RiskDecisionTool,
    SimilarCaseTool,
    TextSentimentTool,
)
from app.services.base import AnalyzerBase


def build_tools(analyzer: AnalyzerBase):
    return [
        ReviewContextTool(),
        TextSentimentTool(analyzer),
        ImageSignalTool(analyzer),
        RatingSignalTool(),
        ModalityConflictTool(),
        DominantModalityTool(),
        SimilarCaseTool(analyzer),
        RiskDecisionTool(),
        OperationSuggestionTool(),
        FinalReportTool(),
    ]
