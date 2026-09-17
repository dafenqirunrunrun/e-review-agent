from __future__ import annotations

from app.agent_trace.synthetic_harness import run_synthetic_agent, synthetic_cases


def test_runtime_trace_off_on_body_and_decision_parity() -> None:
    for case in synthetic_cases(20):
        off = run_synthetic_agent(case, "off")
        on = run_synthetic_agent(case, "memory")
        assert off["businessOutcome"] == on["businessOutcome"]
        assert off["canonicalOutcomeHash"] == on["canonicalOutcomeHash"]
