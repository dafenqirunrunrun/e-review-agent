from typing import Any, Dict

from app.agent_framework import config
from app.agent_framework.fallback import run_legacy_fallback
from app.agent_framework.nodes import build_tools
from app.schemas.review import ReviewAnalyzeRequest, ReviewAnalyzeResponse, WorkflowTraceItem
from app.services.base import AnalyzerBase


def run_agent_graph(payload: ReviewAnalyzeRequest, analyzer: AnalyzerBase, force_framework: bool = False) -> ReviewAnalyzeResponse:
    if not force_framework and not config.status()["enabled"]:
        response = run_legacy_fallback(payload, analyzer)
        response.fallback_used = False
        response.framework = "legacy_rule_agent"
        response.extra = {"framework_enabled": False}
        return response

    if config.status()["api_key_available"] is False and config.status()["provider"] == "openai_agents":
        if not config.status()["fallback_enabled"]:
            raise RuntimeError("OpenAI Agents SDK requires OPENAI_API_KEY")
        return run_legacy_fallback(payload, analyzer)

    try:
        framework = "langgraph" if config.langgraph_available() else "fallback_rule_graph"
        state: Dict[str, Any] = {
            "payload": payload,
            "trace_steps": [],
            "fallback_used": False,
            "framework": framework,
        }
        # If langgraph is installed, this sequential node execution mirrors the same graph nodes.
        # The dependency is optional so local demos still work without network or API keys.
        for tool in build_tools(analyzer):
            state = tool(state)
        return _response_from_state(payload, state, fallback_used=not config.langgraph_available())
    except Exception as exc:
        config.set_last_error(str(exc))
        if config.status()["fallback_enabled"]:
            return run_legacy_fallback(payload, analyzer)
        raise


def _response_from_state(payload: ReviewAnalyzeRequest, state: Dict[str, Any], fallback_used: bool) -> ReviewAnalyzeResponse:
    text = state.get("text_signal", {})
    image = state.get("image_signal", {})
    label = state.get("sentiment_label", text.get("sentiment_label", "neutral"))
    fusion_score = round(
        float(text.get("text_score", 0.5)) * 0.62
        + float(image.get("image_score", 0.5)) * 0.2
        + float(state.get("rating_signal", {}).get("rating_score", 0.5)) * 0.18,
        4,
    )
    scores = _scores(label, fusion_score)
    trace = [
        WorkflowTraceItem(
            node=item.get("node", "unknown"),
            step=item.get("step"),
            agent=item.get("agent"),
            agent_role=item.get("agent_role"),
            agent_goal=item.get("agent_goal"),
            tool_name=item.get("tool_name"),
            framework=item.get("framework", "fallback_rule_graph"),
            status=item.get("status", "success"),
            message=item.get("message") or item.get("output_summary") or "",
            input_summary=item.get("input_summary"),
            output_summary=item.get("output_summary"),
            output=item.get("output"),
            error=item.get("error"),
            duration_ms=item.get("duration_ms"),
        )
        for item in state.get("trace_steps", [])
    ]
    return ReviewAnalyzeResponse(
        review_id=payload.review_id,
        product_id=payload.product_id,
        sentiment_label=label,
        confidence=float(state.get("confidence", text.get("confidence", 0.68))),
        scores=scores,
        evidence=state.get("evidence", []),
        text_score=float(text.get("text_score", 0.5)),
        image_score=float(image.get("image_score", 0.5)),
        fusion_score=fusion_score,
        conflict_score=float(state.get("modality_conflict_score", 0)),
        risk_level=state.get("risk_level", "low"),
        text_evidence=text.get("text_evidence", []),
        image_evidence=image.get("image_evidence", []),
        similar_cases=state.get("similar_cases", []),
        agent_suggestion=state.get("suggestions"),
        workflow_trace=trace,
        modality_conflict=state.get("modality_conflict"),
        dominant_modality=state.get("dominant_modality"),
        framework="langgraph" if config.langgraph_available() else "fallback_rule_graph",
        fallback_used=fallback_used,
        route_decision=state.get("route_decision") or ("human_review" if state.get("risk_level") in {"high", "medium"} else "auto_close"),
        route_reason="visual or text risk requires review" if state.get("risk_level") in {"high", "medium"} else "low risk after multimodal check",
        extra={
            "agent_steps": state.get("trace_steps", []),
            "risk_types": state.get("risk_types", []),
            "langgraph_available": config.langgraph_available(),
            "visual_observability": state.get("visual_observability"),
        },
    )


def _scores(label: str, fusion_score: float):
    positive = max(0.05, min(0.95, fusion_score))
    negative = max(0.05, min(0.95, 1 - fusion_score))
    neutral = max(0.05, min(0.95, 1 - abs(fusion_score - 0.5) * 2))
    if label == "positive":
        positive = max(positive, 0.72)
    elif label == "negative":
        negative = max(negative, 0.72)
    else:
        neutral = max(neutral, 0.72)
    return {
        "positive": round(positive, 4),
        "neutral": round(neutral, 4),
        "negative": round(negative, 4),
    }
