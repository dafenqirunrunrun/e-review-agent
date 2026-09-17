from __future__ import annotations

from app.agent_trace.runtime_harness import run_context_isolation_cases


def test_concurrent_contexts_do_not_contaminate() -> None:
    result = run_context_isolation_cases()
    assert result["traceContamination"] == 0
    assert result["executionContamination"] == 0
    assert result["requestContamination"] == 0
