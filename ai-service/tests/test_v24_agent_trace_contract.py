from __future__ import annotations

from app.agent_trace.contracts import EventType, ExecutionStatus, NodeType, SCHEMA_VERSION
from app.agent_trace.hash_service import TraceHashService
from app.agent_trace.synthetic_harness import run_synthetic_agent, synthetic_cases


def test_trace_contract_and_ids_are_independent() -> None:
    result_a = run_synthetic_agent(synthetic_cases(1)[0], "memory")
    result_b = run_synthetic_agent(synthetic_cases(1)[0], "memory")
    trace_a = result_a["trace"]
    trace_b = result_b["trace"]
    assert trace_a.traceHeader.schemaVersion == SCHEMA_VERSION
    assert trace_a.traceHeader.traceId != trace_b.traceHeader.traceId
    assert trace_a.traceHeader.executionId != trace_b.traceHeader.executionId
    assert result_a["canonicalOutcomeHash"] == result_b["canonicalOutcomeHash"]


def test_required_enums_cover_phase_10a_contract() -> None:
    assert EventType.EXECUTION_STARTED.value
    assert EventType.MODEL_CALL_COMPLETED.value
    assert EventType.TOOL_CALL_FAILED.value
    assert NodeType.EVIDENCE_RETRIEVAL.value
    assert NodeType.EXTERNAL_TOOL.value
    assert ExecutionStatus.FALLBACK_SUCCEEDED.value


def test_canonical_hash_is_stable_and_rank_sensitive() -> None:
    service = TraceHashService("unit-test-key")
    assert service.hash_canonical_object({"b": 2, "a": 1}) == service.hash_canonical_object({"a": 1, "b": 2})
    assert service.hash_ranked_ids(["a", "b"]) != service.hash_ranked_ids(["b", "a"])
    assert service.hash_unordered_ids(["a", "b"]) == service.hash_unordered_ids(["b", "a"])
