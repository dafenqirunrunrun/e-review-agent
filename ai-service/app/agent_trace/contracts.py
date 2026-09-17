from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

SCHEMA_VERSION = "agent-trace.v1"
GENESIS_HASH = "GENESIS"


class EventType(str, Enum):
    EXECUTION_STARTED = "EXECUTION_STARTED"
    REQUEST_VALIDATED = "REQUEST_VALIDATED"
    STATE_TRANSITION = "STATE_TRANSITION"
    NODE_STARTED = "NODE_STARTED"
    NODE_COMPLETED = "NODE_COMPLETED"
    NODE_FAILED = "NODE_FAILED"
    RETRIEVAL_STARTED = "RETRIEVAL_STARTED"
    RETRIEVAL_COMPLETED = "RETRIEVAL_COMPLETED"
    RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
    MODEL_CALL_STARTED = "MODEL_CALL_STARTED"
    MODEL_CALL_COMPLETED = "MODEL_CALL_COMPLETED"
    MODEL_CALL_FAILED = "MODEL_CALL_FAILED"
    TOOL_CALL_STARTED = "TOOL_CALL_STARTED"
    TOOL_CALL_COMPLETED = "TOOL_CALL_COMPLETED"
    TOOL_CALL_FAILED = "TOOL_CALL_FAILED"
    FALLBACK_TRIGGERED = "FALLBACK_TRIGGERED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    HUMAN_REVIEW_REQUESTED = "HUMAN_REVIEW_REQUESTED"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXECUTION_CANCELLED = "EXECUTION_CANCELLED"


class NodeType(str, Enum):
    REQUEST_VALIDATION = "REQUEST_VALIDATION"
    QUERY_CLASSIFICATION = "QUERY_CLASSIFICATION"
    RETRIEVAL_PLANNING = "RETRIEVAL_PLANNING"
    EVIDENCE_RETRIEVAL = "EVIDENCE_RETRIEVAL"
    EVIDENCE_VALIDATION = "EVIDENCE_VALIDATION"
    TASK_REASONING = "TASK_REASONING"
    ANSWER_GENERATION = "ANSWER_GENERATION"
    OUTPUT_VALIDATION = "OUTPUT_VALIDATION"
    FALLBACK = "FALLBACK"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    FINALIZATION = "FINALIZATION"
    EXTERNAL_MODEL = "EXTERNAL_MODEL"
    EXTERNAL_TOOL = "EXTERNAL_TOOL"
    INTERNAL_DETERMINISTIC = "INTERNAL_DETERMINISTIC"


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    FALLBACK_SUCCEEDED = "FALLBACK_SUCCEEDED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    INCOMPLETE = "INCOMPLETE"


@dataclass
class AgentTraceContext:
    schemaVersion: str
    requestId: str
    executionId: str
    traceId: str
    tenantScopeHash: str
    actorContextHash: str
    startedAtUtc: str
    startedMonotonicNs: int
    traceEnabled: bool
    payloadCaptureMode: str
    hashKeyId: str
    sourceTraceId: str | None
    replayId: str | None
    replayMode: str | None
    configurationHash: str
    agentGraphVersion: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentTraceEvent:
    schemaVersion: str
    eventId: str
    sequenceNumber: int
    traceId: str
    executionId: str
    spanId: str
    parentSpanId: str | None
    eventType: str
    nodeName: str
    nodeType: str
    startedAtUtc: str
    completedAtUtc: str
    durationMs: float
    status: str
    inputSummary: dict[str, Any] = field(default_factory=dict)
    outputSummary: dict[str, Any] = field(default_factory=dict)
    decisionSummary: dict[str, Any] = field(default_factory=dict)
    errorSummary: dict[str, Any] = field(default_factory=dict)
    previousEventHash: str = GENESIS_HASH
    eventHash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TraceHeader:
    schemaVersion: str
    traceId: str
    executionId: str
    requestId: str
    agentGraphVersion: str
    configurationHash: str
    environmentFingerprint: str
    buildCommit: str
    startedAtUtc: str
    initialState: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TraceFooter:
    finalState: str
    executionStatus: str
    eventCount: int
    completedAtUtc: str
    durationMs: float
    firstEventHash: str
    lastEventHash: str
    canonicalOutcomeHash: str
    traceIntegrityStatus: str
    incompleteReason: str | None = None
    lastValidSequenceNumber: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentExecutionTrace:
    traceHeader: TraceHeader
    events: list[AgentTraceEvent]
    traceFooter: TraceFooter | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "traceHeader": self.traceHeader.to_dict(),
            "events": [event.to_dict() for event in self.events],
            "traceFooter": self.traceFooter.to_dict() if self.traceFooter else None,
        }
