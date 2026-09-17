from __future__ import annotations

from app.agent_trace.synthetic_harness import benchmark_trace_modes


def test_trace_resource_budget() -> None:
    result = benchmark_trace_modes()
    assert result["caseCount"] == 30
    assert result["modes"]["jsonl"]["traceWriteFailureCount"] == 0
    assert result["jsonlP95LatencyRatio"] <= 20
    assert result["jsonlAbsoluteP95OverheadMs"] <= 50
    assert result["modes"]["jsonl"]["p95TraceSizeBytes"] <= 128 * 1024
