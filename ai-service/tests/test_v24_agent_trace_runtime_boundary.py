from __future__ import annotations

import os


def test_trace_runtime_defaults_are_disabled(monkeypatch) -> None:
    for key in ["AGENT_TRACE_ENABLED", "AGENT_REPLAY_ENABLED", "AGENT_TRACE_PAYLOAD_CAPTURE", "AGENT_TRACE_SINK"]:
        monkeypatch.delenv(key, raising=False)
    assert os.getenv("AGENT_TRACE_ENABLED", "false").lower() == "false"
    assert os.getenv("AGENT_REPLAY_ENABLED", "false").lower() == "false"
    assert os.getenv("AGENT_TRACE_PAYLOAD_CAPTURE", "false").lower() == "false"
    assert os.getenv("AGENT_TRACE_SINK", "none").lower() == "none"
