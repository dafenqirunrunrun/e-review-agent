from __future__ import annotations

import pytest

from app.agent_trace.replay import ReplaySideEffectGuard, replay_trace
from app.agent_trace.synthetic_harness import run_synthetic_agent, synthetic_cases


def test_side_effect_guard_blocks_business_write() -> None:
    guard = ReplaySideEffectGuard()
    with pytest.raises(RuntimeError):
        guard.block("Business Write Adapter", {"orderId": "synthetic"})
    assert guard.attempt_count == 1
    assert guard.blocked_count == 1


def test_replay_records_blocked_side_effect_attempt() -> None:
    result = run_synthetic_agent(synthetic_cases(1)[0], "memory")
    replay = replay_trace(result["trace"], result["canonicalOutcomeHash"], simulate_side_effect=True)
    assert replay.sideEffectAttemptCount == 1
    assert replay.blockedSideEffectCount == 1
