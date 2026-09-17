from __future__ import annotations

from app.agent_trace.runtime_context import REPLAY_HTTP_ROUTES_ENABLED
from app.agent_trace.replay import ReplaySideEffectGuard


def test_replay_is_not_exposed_as_runtime_http_route() -> None:
    assert REPLAY_HTTP_ROUTES_ENABLED is False


def test_replay_side_effect_guard_still_blocks() -> None:
    guard = ReplaySideEffectGuard()
    try:
        guard.block("External Tool Adapter", {"synthetic": True})
    except RuntimeError:
        pass
    assert guard.attempt_count == 1
    assert guard.blocked_count == 1
