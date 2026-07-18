import importlib.util

from app.core.config import settings


LAST_ERROR = None


def langgraph_available() -> bool:
    return importlib.util.find_spec("langgraph") is not None


def openai_agents_available() -> bool:
    return importlib.util.find_spec("agents") is not None or importlib.util.find_spec("openai") is not None


def status() -> dict:
    if not settings.agent_framework_enabled:
        current_mode = "legacy_rule_agent"
    elif langgraph_available():
        current_mode = "langgraph"
    elif settings.agent_framework_fallback_enabled:
        current_mode = "fallback_rule_graph"
    else:
        current_mode = "unavailable"
    return {
        "enabled": settings.agent_framework_enabled,
        "provider": settings.agent_framework_provider,
        "langgraph_available": langgraph_available(),
        "openai_agents_available": openai_agents_available(),
        "fallback_enabled": settings.agent_framework_fallback_enabled,
        "api_key_available": settings.openai_api_key_available,
        "current_mode": current_mode,
        "last_error": LAST_ERROR,
    }


def set_last_error(message):
    global LAST_ERROR
    LAST_ERROR = message
