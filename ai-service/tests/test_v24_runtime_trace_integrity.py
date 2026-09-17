from __future__ import annotations

from app.agent_trace.runtime_harness import run_runtime_trace_fixture_suite


def test_runtime_trace_integrity_summary() -> None:
    result = run_runtime_trace_fixture_suite()
    assert result["traceIntegrityPassCount"] == result["traceCount"]
    assert result["businessWriteCount"] == 0
    assert result["externalToolCallCount"] == 0
