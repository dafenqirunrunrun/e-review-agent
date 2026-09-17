from __future__ import annotations

from app.agent_trace.replay import replay_trace
from app.agent_trace.synthetic_harness import run_synthetic_agent, synthetic_cases


def test_structural_replay_matches_outcome_hash() -> None:
    result = run_synthetic_agent(synthetic_cases(1)[0], "memory")
    replay = replay_trace(result["trace"], result["canonicalOutcomeHash"])
    assert replay.structuralReplayPass is True
    assert replay.outcomeHashMatch is True
