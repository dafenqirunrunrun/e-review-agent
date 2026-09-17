from __future__ import annotations

import json

from app.agent_trace.redactor import AgentTraceRedactor
from app.agent_trace.hash_service import TraceHashService
from app.agent_trace.synthetic_harness import run_synthetic_agent, synthetic_cases


def test_sensitive_fields_are_hmac_summarized() -> None:
    redactor = AgentTraceRedactor(TraceHashService("unit-test-key"))
    summary = redactor.summarize(
        {
            "password": "do-not-leak",
            "Authorization": "Bearer secret-token",
            "email": "person@example.test",
            "safeCount": 3,
        }
    )
    rendered = json.dumps(summary, ensure_ascii=False)
    assert "do-not-leak" not in rendered
    assert "secret-token" not in rendered
    assert "person@example.test" not in rendered
    assert rendered.count("hmacSha256") >= 3


def test_trace_does_not_store_raw_query_prompt_evidence_or_tool_args() -> None:
    case = synthetic_cases(1)[0]
    result = run_synthetic_agent(case, "memory")
    rendered = json.dumps(result["trace"].to_dict(), ensure_ascii=False)
    assert case["query"] not in rendered
    assert "Bearer synthetic-secret" not in rendered
    assert "完整Prompt" not in rendered
    assert "完整Evidence" not in rendered
