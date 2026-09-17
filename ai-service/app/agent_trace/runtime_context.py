from __future__ import annotations

import contextvars
import hmac
import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.agent_trace.contracts import SCHEMA_VERSION

HEADER_REQUEST_ID = "X-EReview-Request-Id"
HEADER_TRACE_ID = "X-EReview-Trace-Id"
HEADER_EXECUTION_ID = "X-EReview-Execution-Id"
HEADER_TRACE_SCHEMA = "X-EReview-Trace-Schema"
HEADER_ISSUED_AT = "X-EReview-Trace-Issued-At"
HEADER_CALLER = "X-EReview-Trace-Caller"
HEADER_SIGNATURE = "X-EReview-Trace-Signature"

REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
REPLAY_HTTP_ROUTES_ENABLED = False


@dataclass(frozen=True)
class RuntimeTraceContext:
    request_id: str
    trace_id: str
    execution_id: str
    trace_schema_version: str
    caller_service: str
    issued_at_utc: str
    signature: str
    propagation_trust_status: str
    trace_enabled: bool


_current_context: contextvars.ContextVar[RuntimeTraceContext | None] = contextvars.ContextVar(
    "e_review_agent_trace_context",
    default=None,
)


def current_trace_context() -> RuntimeTraceContext | None:
    return _current_context.get()


def validate_or_generate_request_id(value: str | None) -> tuple[str, bool]:
    if value and REQUEST_ID_RE.match(value):
        return value, False
    return uuid.uuid4().hex, True


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _signing_payload(
    request_id: str,
    trace_id: str,
    execution_id: str,
    trace_schema_version: str,
    caller_service: str,
    issued_at_utc: str,
) -> str:
    return "\n".join([request_id, trace_id, execution_id, trace_schema_version, caller_service, issued_at_utc])


def sign_context(
    request_id: str,
    trace_id: str,
    execution_id: str,
    trace_schema_version: str,
    caller_service: str,
    issued_at_utc: str,
    key: str | None = None,
) -> str:
    secret = key or os.getenv("AGENT_TRACE_CONTEXT_HMAC_KEY") or "synthetic-context-key"
    return hmac.new(
        secret.encode("utf-8"),
        _signing_payload(request_id, trace_id, execution_id, trace_schema_version, caller_service, issued_at_utc).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def context_headers(context: RuntimeTraceContext) -> dict[str, str]:
    return {
        HEADER_REQUEST_ID: context.request_id,
        HEADER_TRACE_ID: context.trace_id,
        HEADER_EXECUTION_ID: context.execution_id,
        HEADER_TRACE_SCHEMA: context.trace_schema_version,
        HEADER_ISSUED_AT: context.issued_at_utc,
        HEADER_CALLER: context.caller_service,
        HEADER_SIGNATURE: context.signature,
    }


def create_local_context(request_id: str | None = None, caller_service: str = "fastapi") -> RuntimeTraceContext:
    safe_request_id, _ = validate_or_generate_request_id(request_id)
    trace_id = uuid.uuid4().hex
    execution_id = uuid.uuid4().hex
    issued = utc_now()
    signature = sign_context(safe_request_id, trace_id, execution_id, SCHEMA_VERSION, caller_service, issued)
    return RuntimeTraceContext(
        request_id=safe_request_id,
        trace_id=trace_id,
        execution_id=execution_id,
        trace_schema_version=SCHEMA_VERSION,
        caller_service=caller_service,
        issued_at_utc=issued,
        signature=signature,
        propagation_trust_status="LOCAL_GENERATED",
        trace_enabled=os.getenv("AGENT_TRACE_ENABLED", "false").lower() == "true",
    )


def parse_inbound_context(headers: Mapping[str, str]) -> RuntimeTraceContext:
    request_id, replaced = validate_or_generate_request_id(headers.get(HEADER_REQUEST_ID) or headers.get(HEADER_REQUEST_ID.lower()))
    trace_id = headers.get(HEADER_TRACE_ID) or headers.get(HEADER_TRACE_ID.lower()) or ""
    execution_id = headers.get(HEADER_EXECUTION_ID) or headers.get(HEADER_EXECUTION_ID.lower()) or ""
    schema = headers.get(HEADER_TRACE_SCHEMA) or headers.get(HEADER_TRACE_SCHEMA.lower()) or SCHEMA_VERSION
    issued = headers.get(HEADER_ISSUED_AT) or headers.get(HEADER_ISSUED_AT.lower()) or ""
    caller = headers.get(HEADER_CALLER) or headers.get(HEADER_CALLER.lower()) or "unknown"
    signature = headers.get(HEADER_SIGNATURE) or headers.get(HEADER_SIGNATURE.lower()) or ""
    if replaced or not trace_id or not execution_id or not issued or not signature:
        ctx = create_local_context(request_id)
        return _replace_status(ctx, "REJECTED_AND_REGENERATED")
    expected = sign_context(request_id, trace_id, execution_id, schema, caller, issued)
    if not hmac.compare_digest(signature, expected):
        ctx = create_local_context(request_id)
        return _replace_status(ctx, "REJECTED_AND_REGENERATED")
    return RuntimeTraceContext(
        request_id=request_id,
        trace_id=trace_id,
        execution_id=execution_id,
        trace_schema_version=schema,
        caller_service=caller,
        issued_at_utc=issued,
        signature=signature,
        propagation_trust_status="VERIFIED",
        trace_enabled=os.getenv("AGENT_TRACE_ENABLED", "false").lower() == "true",
    )


def _replace_status(context: RuntimeTraceContext, status: str) -> RuntimeTraceContext:
    return RuntimeTraceContext(
        request_id=context.request_id,
        trace_id=context.trace_id,
        execution_id=context.execution_id,
        trace_schema_version=context.trace_schema_version,
        caller_service=context.caller_service,
        issued_at_utc=context.issued_at_utc,
        signature=context.signature,
        propagation_trust_status=status,
        trace_enabled=context.trace_enabled,
    )


class AgentTraceContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        context = parse_inbound_context(request.headers)
        token = _current_context.set(context)
        try:
            response: Response = await call_next(request)
            response.headers[HEADER_REQUEST_ID] = context.request_id
            response.headers[HEADER_TRACE_ID] = context.trace_id
            return response
        finally:
            _current_context.reset(token)
