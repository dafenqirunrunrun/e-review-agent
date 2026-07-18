from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agent.human_review import HumanReviewRouter
from app.agent.tool_registry import ToolRegistry
from app.config.enterprise_runtime_config import EnterpriseRuntimeConfig
from app.llm.enterprise_providers import EnterpriseTextRequest, TextProviderFactory
from app.rag.evidence_verifier import EvidenceVerifier
from app.rag.query_pipeline import QueryPipeline


@dataclass
class GovernedAgentState:
    steps: list[str] = field(default_factory=list)
    tool_calls: int = 0
    tool_audit: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)


class GovernedAgent:
    NODES = [
        "input_guard",
        "intent_router",
        "query_planner",
        "retrieve",
        "rerank",
        "verify_evidence",
        "decide",
        "policy_guard",
        "human_review_router",
        "response_assembler",
        "audit_sink",
    ]

    def __init__(self, config: EnterpriseRuntimeConfig | None = None, tools: ToolRegistry | None = None):
        self.config = config or EnterpriseRuntimeConfig()
        self.tools = tools or ToolRegistry()
        self.query_pipeline = QueryPipeline()
        self.evidence_verifier = EvidenceVerifier()
        self.human_router = HumanReviewRouter()

    def run(self, request: EnterpriseTextRequest, chunks: list[dict] | None = None) -> GovernedAgentState:
        state = GovernedAgentState()
        for node in self.NODES:
            if len(state.steps) >= self.config.max_agent_steps + 3:
                state.errors.append("MAX_STEP_VIOLATION_PREVENTED")
                break
            state.steps.append(node)
            if node == "query_planner":
                plan = self.query_pipeline.plan(request.review_text)
                state.output["query_plan"] = {"intent": plan.intent, "blocked": plan.blocked}
                if plan.blocked:
                    state.errors.append(plan.block_reason or "QUERY_BLOCKED")
                    state.output["input_blocked"] = True
            elif node == "retrieve":
                if self._skip_if_blocked(state, node):
                    continue
                self._call_tool(state, "search_cases")
            elif node == "verify_evidence":
                if self._skip_if_blocked(state, node):
                    continue
                self._call_tool(state, "verify_evidence")
                verification = self.evidence_verifier.verify(
                    tenant_id=request.tenant_id,
                    chunks=chunks or [],
                    evidence=[],
                    claims=[],
                    risk_level="low",
                )
                state.output["evidence_coverage"] = verification.evidence_coverage
            elif node == "decide":
                if self._skip_if_blocked(state, node):
                    continue
                result = TextProviderFactory(self.config).create().analyze(request)
                state.output["decision"] = result.decision.model_dump(mode="json")
                state.output["fallback"] = result.fallback_used
            elif node == "human_review_router":
                decision = state.output.get("decision") or {}
                route = self.human_router.route(
                    risk_level=str(decision.get("risk_level") or "low"),
                    fallback=bool(state.output.get("fallback")),
                    insufficient_evidence=bool(decision.get("need_human_review")) and str(decision.get("risk_level") or "low") != "high",
                    prompt_injection=bool(state.errors),
                )
                state.output["human_review"] = route.__dict__
        return state

    def _call_tool(self, state: GovernedAgentState, name: str) -> None:
        if state.tool_calls >= self.config.max_tool_calls:
            state.errors.append("MAX_TOOL_CALLS_REACHED")
            state.tool_audit.append({"tool": name, "status": "SKIPPED_MAX_TOOL_CALLS"})
            return
        tool = self.tools.get(name)
        if tool.timeout_ms > self.config.tool_timeout_ms:
            state.errors.append("TOOL_TIMEOUT_POLICY_VIOLATION")
            state.tool_audit.append({"tool": name, "status": "BLOCKED_TIMEOUT_POLICY"})
            return
        state.tool_calls += 1
        state.tool_audit.append(
            {
                "tool": tool.name,
                "status": "ALLOWED",
                "risk_level": tool.risk_level,
                "tenant_scope": tool.tenant_scope,
                "audit_policy": tool.audit_policy,
            }
        )

    def _skip_if_blocked(self, state: GovernedAgentState, node: str) -> bool:
        if not state.output.get("input_blocked"):
            return False
        state.tool_audit.append({"node": node, "status": "SKIPPED_INPUT_BLOCKED"})
        return True
