from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.agent_trace.contracts import (
    GENESIS_HASH,
    SCHEMA_VERSION,
    AgentExecutionTrace,
    AgentTraceContext,
    AgentTraceEvent,
    EventType,
    ExecutionStatus,
    NodeType,
    TraceFooter,
    TraceHeader,
)
from app.agent_trace.hash_service import TraceHashService
from app.agent_trace.redactor import AgentTraceRedactor
from app.agent_trace.sinks import AgentTraceSink, NullTraceSink


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AgentTraceRecorder:
    def __init__(
        self,
        *,
        request_id: str | None = None,
        tenant_scope: str = "synthetic-tenant",
        actor_context: str = "synthetic-actor",
        trace_enabled: bool | None = None,
        payload_capture_mode: str = "summary_only",
        hmac_key: str | None = None,
        hash_key_id: str = "qualification-key-v1",
        configuration: dict[str, Any] | None = None,
        agent_graph_version: str = "synthetic-agent-graph-v1",
        sink: AgentTraceSink | None = None,
        source_trace_id: str | None = None,
        replay_id: str | None = None,
        replay_mode: str | None = None,
    ):
        self.hash_service = TraceHashService(hmac_key or os.getenv("AGENT_TRACE_HMAC_KEY") or "synthetic-qualification-key")
        self.redactor = AgentTraceRedactor(self.hash_service)
        self.trace_write_failure_count = 0
        enabled = trace_enabled if trace_enabled is not None else os.getenv("AGENT_TRACE_ENABLED", "false").lower() == "true"
        self.sink = sink or NullTraceSink()
        started = utc_now()
        self.context = AgentTraceContext(
            schemaVersion=SCHEMA_VERSION,
            requestId=request_id or uuid.uuid4().hex,
            executionId=uuid.uuid4().hex,
            traceId=uuid.uuid4().hex,
            tenantScopeHash=self.hash_service.hash_sensitive_text(tenant_scope),
            actorContextHash=self.hash_service.hash_sensitive_text(actor_context),
            startedAtUtc=started,
            startedMonotonicNs=time.perf_counter_ns(),
            traceEnabled=enabled,
            payloadCaptureMode=payload_capture_mode,
            hashKeyId=hash_key_id,
            sourceTraceId=source_trace_id,
            replayId=replay_id,
            replayMode=replay_mode,
            configurationHash=self.hash_service.hash_canonical_object(configuration or {}),
            agentGraphVersion=agent_graph_version,
        )
        self.trace = AgentExecutionTrace(
            traceHeader=TraceHeader(
                schemaVersion=SCHEMA_VERSION,
                traceId=self.context.traceId,
                executionId=self.context.executionId,
                requestId=self.context.requestId,
                agentGraphVersion=agent_graph_version,
                configurationHash=self.context.configurationHash,
                environmentFingerprint=self.hash_service.hash_canonical_object({"runtime": "python", "mode": "qualification"}),
                buildCommit=os.getenv("BUILD_COMMIT", "unversioned"),
                startedAtUtc=started,
                initialState=ExecutionStatus.PENDING.value,
            ),
            events=[],
        )
        self._sequence = 0
        self._last_hash = GENESIS_HASH
        self._open_spans: dict[str, str] = {}
        self._terminal_spans: set[str] = set()
        self._safe_sink_call(self.sink.start_trace, self.trace)

    def record(
        self,
        event_type: EventType,
        node_name: str,
        node_type: NodeType,
        *,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        status: ExecutionStatus = ExecutionStatus.RUNNING,
        input_summary: dict[str, Any] | None = None,
        output_summary: dict[str, Any] | None = None,
        decision_summary: dict[str, Any] | None = None,
        error_summary: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
    ) -> AgentTraceEvent:
        self._sequence += 1
        current_span_id = span_id or uuid.uuid4().hex
        event = AgentTraceEvent(
            schemaVersion=SCHEMA_VERSION,
            eventId=uuid.uuid4().hex,
            sequenceNumber=self._sequence,
            traceId=self.context.traceId,
            executionId=self.context.executionId,
            spanId=current_span_id,
            parentSpanId=parent_span_id,
            eventType=event_type.value,
            nodeName=node_name,
            nodeType=node_type.value,
            startedAtUtc=utc_now(),
            completedAtUtc=utc_now(),
            durationMs=max(0.0, duration_ms),
            status=status.value,
            inputSummary=self.redactor.summarize(input_summary or {}),
            outputSummary=self.redactor.summarize(output_summary or {}),
            decisionSummary=self.redactor.summarize(decision_summary or {}),
            errorSummary=self.redactor.summarize(error_summary or {}),
            previousEventHash=self._last_hash,
        )
        event.eventHash = self.hash_service.hash_event(self._last_hash, event.to_dict())
        self._last_hash = event.eventHash
        self.trace.events.append(event)
        self._update_span_state(event)
        self._safe_sink_call(self.sink.append_event, event)
        return event

    def complete(self, final_state: str, status: ExecutionStatus, outcome: dict[str, Any]) -> AgentExecutionTrace:
        completed = utc_now()
        duration_ms = (time.perf_counter_ns() - self.context.startedMonotonicNs) / 1_000_000
        first_hash = self.trace.events[0].eventHash if self.trace.events else GENESIS_HASH
        self.trace.traceFooter = TraceFooter(
            finalState=final_state,
            executionStatus=status.value,
            eventCount=len(self.trace.events),
            completedAtUtc=completed,
            durationMs=duration_ms,
            firstEventHash=first_hash,
            lastEventHash=self._last_hash,
            canonicalOutcomeHash=self.canonical_outcome_hash(outcome),
            traceIntegrityStatus="VALID",
            incompleteReason=None,
            lastValidSequenceNumber=self._sequence,
        )
        self._safe_sink_call(self.sink.complete_trace, self.trace)
        return self.trace

    def canonical_outcome_hash(self, outcome: dict[str, Any]) -> str:
        excluded = {"traceId", "executionId", "spanId", "eventId", "timestamp", "durationMs", "localPath"}
        def strip(value: Any) -> Any:
            if isinstance(value, dict):
                return {k: strip(v) for k, v in value.items() if k not in excluded}
            if isinstance(value, list):
                return [strip(v) for v in value]
            return value
        return self.hash_service.hash_canonical_object(strip(outcome))

    def _update_span_state(self, event: AgentTraceEvent) -> None:
        if event.eventType.endswith("_STARTED"):
            if event.spanId in self._open_spans or event.spanId in self._terminal_spans:
                raise ValueError("duplicate span start")
            self._open_spans[event.spanId] = event.eventType
        if event.eventType.endswith("_COMPLETED") or event.eventType.endswith("_FAILED"):
            if event.spanId in self._terminal_spans:
                raise ValueError("span already terminal")
            self._terminal_spans.add(event.spanId)
            self._open_spans.pop(event.spanId, None)

    def _safe_sink_call(self, func: Any, *args: Any) -> None:
        try:
            func(*args)
        except Exception:
            self.trace_write_failure_count += 1
