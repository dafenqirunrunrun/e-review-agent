from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.observability.langfuse_sidecar import LangfuseTelemetry


router = APIRouter(prefix="/telemetry", tags=["telemetry"])


class HumanFeedbackRequest(BaseModel):
    langfuseTraceId: str = Field(min_length=1)
    humanDecision: str = Field(min_length=1)
    aiDecision: str = Field(min_length=1)
    overrideReasonCode: str = ""


@router.post("/human-feedback")
def human_feedback(payload: HumanFeedbackRequest) -> dict[str, bool]:
    return {"recorded": LangfuseTelemetry.record_human_feedback(
        trace_id=payload.langfuseTraceId,
        human_decision=payload.humanDecision,
        ai_decision=payload.aiDecision,
        override_reason_code=payload.overrideReasonCode,
    )}
