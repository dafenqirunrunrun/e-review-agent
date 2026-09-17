from __future__ import annotations

from fastapi.testclient import TestClient

from app.agent_trace.runtime_context import HEADER_REQUEST_ID, HEADER_TRACE_ID, current_trace_context
from app.main import app


def test_fastapi_response_headers_and_context_cleanup() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health", headers={HEADER_REQUEST_ID: "req-12345678"})
    assert response.status_code == 200
    assert response.headers[HEADER_REQUEST_ID] == "req-12345678"
    assert response.headers[HEADER_TRACE_ID]
    assert current_trace_context() is None


def test_invalid_inbound_trace_header_does_not_fail_business_request() -> None:
    client = TestClient(app)
    response = client.get(
        "/api/v1/health",
        headers={
            HEADER_REQUEST_ID: "bad id",
            HEADER_TRACE_ID: "attacker-trace",
            "X-EReview-Trace-Signature": "bad",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers[HEADER_TRACE_ID] != "attacker-trace"
