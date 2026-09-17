from __future__ import annotations

from app.agent_trace.contracts import SCHEMA_VERSION
from app.agent_trace.runtime_context import (
    HEADER_CALLER,
    HEADER_EXECUTION_ID,
    HEADER_ISSUED_AT,
    HEADER_REQUEST_ID,
    HEADER_SIGNATURE,
    HEADER_TRACE_ID,
    HEADER_TRACE_SCHEMA,
    create_local_context,
    parse_inbound_context,
    sign_context,
    validate_or_generate_request_id,
)


def test_request_id_validation_replaces_invalid_value() -> None:
    request_id, replaced = validate_or_generate_request_id("bad request id with spaces")
    assert replaced is True
    assert " " not in request_id


def test_signed_internal_context_is_verified() -> None:
    context = create_local_context("req-12345678", "spring-admin")
    headers = {
        HEADER_REQUEST_ID: context.request_id,
        HEADER_TRACE_ID: context.trace_id,
        HEADER_EXECUTION_ID: context.execution_id,
        HEADER_TRACE_SCHEMA: context.trace_schema_version,
        HEADER_ISSUED_AT: context.issued_at_utc,
        HEADER_CALLER: context.caller_service,
        HEADER_SIGNATURE: context.signature,
    }
    parsed = parse_inbound_context(headers)
    assert parsed.propagation_trust_status == "VERIFIED"
    assert parsed.trace_id == context.trace_id


def test_invalid_signature_is_rejected_and_regenerated() -> None:
    headers = {
        HEADER_REQUEST_ID: "req-12345678",
        HEADER_TRACE_ID: "attacker-trace",
        HEADER_EXECUTION_ID: "attacker-exec",
        HEADER_TRACE_SCHEMA: SCHEMA_VERSION,
        HEADER_ISSUED_AT: "2026-07-26T00:00:00Z",
        HEADER_CALLER: "external",
        HEADER_SIGNATURE: "bad",
    }
    parsed = parse_inbound_context(headers)
    assert parsed.propagation_trust_status == "REJECTED_AND_REGENERATED"
    assert parsed.trace_id != "attacker-trace"


def test_signature_changes_when_execution_changes() -> None:
    first = sign_context("req-12345678", "trace-a", "exec-a", SCHEMA_VERSION, "spring-admin", "2026-07-26T00:00:00Z", "k")
    second = sign_context("req-12345678", "trace-a", "exec-b", SCHEMA_VERSION, "spring-admin", "2026-07-26T00:00:00Z", "k")
    assert first != second
