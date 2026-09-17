from __future__ import annotations

from app.agent_trace.runtime_harness import run_runtime_resource_suite


def test_runtime_resource_synthetic_budget() -> None:
    result = run_runtime_resource_suite()
    assert result["p95TraceSizeBytes"] <= 128 * 1024
    assert result["pythonMemoryDeltaMb"] <= 64
    assert result["traceWriteFailureCount"] == 0
