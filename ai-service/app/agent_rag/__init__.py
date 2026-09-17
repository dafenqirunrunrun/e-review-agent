"""Governed Agent-RAG Phase 1 runtime."""

from app.agent_rag.contracts import AgentRagRequest, AgentRagResult

__all__ = ["AgentRagRequest", "AgentRagResult", "AgentRagRuntime"]


def __getattr__(name: str):
    if name == "AgentRagRuntime":
        from app.agent_rag.runtime import AgentRagRuntime

        return AgentRagRuntime
    raise AttributeError(name)
