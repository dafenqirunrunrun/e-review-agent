"""Bounded, in-process context for the agentic review workflow.

This is deliberately not a cross-review memory store.  A review workflow owns
one instance, so a previous review can never influence a new governance
decision.  The memory package is advisory context for future LLM-backed nodes;
the deterministic governance decision continues to use its existing inputs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


def estimate_tokens(value: Any) -> int:
    """A stable, dependency-free budget estimate suitable for bounded context."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    cjk = sum("\u4e00" <= character <= "\u9fff" for character in text)
    other = max(0, len(text) - cjk)
    return max(1, cjk + (other + 3) // 4)


@dataclass
class GovernanceStructuredMemory:
    riskTypes: list[str] = field(default_factory=list)
    evidenceIds: list[str] = field(default_factory=list)
    reflectionStatus: str = "unchecked"
    humanDecision: str = "pending"
    workflowState: str = "initialized"


@dataclass
class IterationSummary:
    goal: str
    confirmedFacts: list[str]
    evidenceUsed: list[str]
    unresolvedIssues: list[str]
    nextAction: str


@dataclass
class MemoryTurn:
    node: str
    content: dict[str, Any]


class GovernanceMemory:
    """Rolling-window memory with explicit priority-aware context construction."""

    def __init__(self, *, goal: str, recent_turns: int, max_context_tokens: int):
        self.goal = goal
        self.recent_turns = recent_turns
        self.max_context_tokens = max_context_tokens
        self.structured = GovernanceStructuredMemory()
        self.summaries: list[IterationSummary] = []
        self.turns: list[MemoryTurn] = []

    def update_state(
        self,
        *,
        risk_types: list[str] | None = None,
        evidence_ids: list[str] | None = None,
        reflection_status: str | None = None,
        human_decision: str | None = None,
        workflow_state: str | None = None,
    ) -> None:
        if risk_types is not None:
            self.structured.riskTypes = sorted(set(risk_types))
        if evidence_ids is not None:
            self.structured.evidenceIds = list(dict.fromkeys(evidence_ids))
        if reflection_status is not None:
            self.structured.reflectionStatus = reflection_status
        if human_decision is not None:
            self.structured.humanDecision = human_decision
        if workflow_state is not None:
            self.structured.workflowState = workflow_state

    def record_turn(self, node: str, **content: Any) -> None:
        # Do not retain raw review content or full policy text in transient context.
        self.turns.append(MemoryTurn(node=node, content=content))

    def add_iteration_summary(
        self,
        *,
        confirmed_facts: list[str],
        evidence_used: list[str],
        unresolved_issues: list[str],
        next_action: str,
    ) -> None:
        self.summaries.append(
            IterationSummary(
                goal=self.goal,
                confirmedFacts=confirmed_facts,
                evidenceUsed=evidence_used,
                unresolvedIssues=unresolved_issues,
                nextAction=next_action,
            )
        )

    def context(self) -> dict[str, Any]:
        """Build a budgeted context: state, latest summary, then recent turns."""
        selected: dict[str, Any] = {"structuredMemory": asdict(self.structured)}
        used = estimate_tokens(selected)
        selected_summaries: list[dict[str, Any]] = []
        for summary in reversed(self.summaries):
            row = asdict(summary)
            cost = estimate_tokens(row)
            if used + cost > self.max_context_tokens:
                continue
            selected_summaries.insert(0, row)
            used += cost
        selected_turns: list[dict[str, Any]] = []
        for turn in reversed(self.turns[-self.recent_turns :]):
            row = asdict(turn)
            cost = estimate_tokens(row)
            if used + cost > self.max_context_tokens:
                continue
            selected_turns.insert(0, row)
            used += cost
        selected["iterationSummaries"] = selected_summaries
        selected["recentTurns"] = selected_turns
        selected["budget"] = {
            "maxContextTokens": self.max_context_tokens,
            "estimatedTokens": used,
            "recentTurnsConfigured": self.recent_turns,
            "droppedTurnCount": max(0, len(self.turns) - len(selected_turns)),
        }
        return selected

    def diagnostics(self) -> dict[str, Any]:
        raw = {"turns": [asdict(turn) for turn in self.turns], "summaries": [asdict(item) for item in self.summaries], "structuredMemory": asdict(self.structured)}
        compressed = self.context()
        before = estimate_tokens(raw)
        after = estimate_tokens(compressed)
        return {
            "beforeTokens": before,
            "afterTokens": after,
            "reductionPercent": round((1 - after / before) * 100, 2) if before else 0.0,
            "summaryCount": len(self.summaries),
            "turnCount": len(self.turns),
        }
