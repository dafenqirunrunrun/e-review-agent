from __future__ import annotations

from app.agent_trace.synthetic_harness import run_synthetic_agent, synthetic_cases


def test_trace_off_on_business_behavior_parity() -> None:
    for case in synthetic_cases(30):
        off = run_synthetic_agent(case, "off")
        memory = run_synthetic_agent(case, "memory")
        assert off["businessOutcome"] == memory["businessOutcome"]
        assert off["canonicalOutcomeHash"] == memory["canonicalOutcomeHash"]


def test_node_sequence_and_fallback_decision_match() -> None:
    case = synthetic_cases(10)[-1]
    off = run_synthetic_agent(case, "off")
    memory = run_synthetic_agent(case, "memory")
    assert off["businessOutcome"]["orderedNodeTypeSequence"] == memory["businessOutcome"]["orderedNodeTypeSequence"]
    assert off["businessOutcome"]["fallbackReasonCodes"] == memory["businessOutcome"]["fallbackReasonCodes"]
