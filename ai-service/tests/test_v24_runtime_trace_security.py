from __future__ import annotations

import json

from app.agent_trace.synthetic_harness import run_synthetic_agent, synthetic_cases


def test_runtime_trace_safe_summary_has_no_raw_payload() -> None:
    case = synthetic_cases(1)[0]
    result = run_synthetic_agent(case, "memory")
    rendered = json.dumps(result["trace"].to_dict(), ensure_ascii=False)
    assert case["query"] not in rendered
    assert "Bearer synthetic-secret" not in rendered
    assert "hmacSha256" in rendered
