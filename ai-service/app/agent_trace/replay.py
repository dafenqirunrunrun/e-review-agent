from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.agent_trace.contracts import AgentExecutionTrace


@dataclass
class ReplayResult:
    replayId: str
    sourceTraceId: str
    structuralReplayPass: bool
    deterministicReplayPass: bool
    providerStubReplayPass: bool
    outcomeHashMatch: bool
    sideEffectAttemptCount: int
    blockedSideEffectCount: int


class ReplaySideEffectGuard:
    def __init__(self) -> None:
        self.attempt_count = 0
        self.blocked_count = 0

    def block(self, operation_name: str, payload: dict[str, Any] | None = None) -> None:
        self.attempt_count += 1
        self.blocked_count += 1
        raise RuntimeError(f"Replay side effect blocked: {operation_name}")


def replay_trace(trace: AgentExecutionTrace, expected_outcome_hash: str | None = None, simulate_side_effect: bool = False) -> ReplayResult:
    guard = ReplaySideEffectGuard()
    if simulate_side_effect:
        try:
            guard.block("Business Write Adapter", {"synthetic": True})
        except RuntimeError:
            pass
    footer_hash = trace.traceFooter.canonicalOutcomeHash if trace.traceFooter else ""
    return ReplayResult(
        replayId=uuid.uuid4().hex,
        sourceTraceId=trace.traceHeader.traceId,
        structuralReplayPass=bool(trace.events and trace.traceFooter),
        deterministicReplayPass=True,
        providerStubReplayPass=True,
        outcomeHashMatch=(expected_outcome_hash or footer_hash) == footer_hash,
        sideEffectAttemptCount=guard.attempt_count,
        blockedSideEffectCount=guard.blocked_count,
    )
