from __future__ import annotations

from dataclasses import dataclass, field

from app.agent_trace.contracts import GENESIS_HASH, AgentExecutionTrace
from app.agent_trace.hash_service import TraceHashService


@dataclass
class TraceIntegrityResult:
    valid: bool
    failureCodes: list[str] = field(default_factory=list)
    eventCount: int = 0
    duplicateEventIdCount: int = 0
    duplicateSpanIdCount: int = 0
    orphanSpanCount: int = 0
    unpairedSpanCount: int = 0
    sequenceGapCount: int = 0
    hashChainFailureCount: int = 0
    traceFooterMismatchCount: int = 0


class TraceIntegrityVerifier:
    def __init__(self, hash_service: TraceHashService):
        self.hash_service = hash_service

    def verify(self, trace: AgentExecutionTrace) -> TraceIntegrityResult:
        result = TraceIntegrityResult(valid=True, eventCount=len(trace.events))
        seen_event_ids: set[str] = set()
        span_starts: set[str] = set()
        span_terms: set[str] = set()
        previous_hash = GENESIS_HASH
        expected_sequence = 1
        for event in trace.events:
            if event.eventId in seen_event_ids:
                result.duplicateEventIdCount += 1
                result.failureCodes.append("EVENT_INSERTION_DETECTED")
            seen_event_ids.add(event.eventId)
            if event.sequenceNumber != expected_sequence:
                result.sequenceGapCount += 1
                result.failureCodes.append("SEQUENCE_NUMBER_GAP")
            expected_sequence += 1
            if event.previousEventHash != previous_hash:
                result.hashChainFailureCount += 1
                result.failureCodes.append("PREVIOUS_HASH_MISMATCH")
            recalculated = self.hash_service.hash_event(event.previousEventHash, event.to_dict())
            if recalculated != event.eventHash:
                result.hashChainFailureCount += 1
                result.failureCodes.append("EVENT_HASH_MISMATCH")
            if event.parentSpanId and event.parentSpanId not in span_starts:
                result.orphanSpanCount += 1
                result.failureCodes.append("EVENT_REORDERING_DETECTED")
            if event.eventType.endswith("_STARTED"):
                if event.spanId in span_starts:
                    result.duplicateSpanIdCount += 1
                    result.failureCodes.append("SEQUENCE_NUMBER_DUPLICATE")
                span_starts.add(event.spanId)
            if event.eventType.endswith("_COMPLETED") or event.eventType.endswith("_FAILED"):
                span_terms.add(event.spanId)
            previous_hash = event.eventHash
        result.unpairedSpanCount = len(span_starts - span_terms)
        if result.unpairedSpanCount:
            result.failureCodes.append("EVENT_DELETION_DETECTED")
        if trace.traceFooter:
            if trace.traceFooter.eventCount != len(trace.events) or trace.traceFooter.lastEventHash != previous_hash:
                result.traceFooterMismatchCount += 1
                result.failureCodes.append("TRACE_FOOTER_MISMATCH")
        else:
            result.traceFooterMismatchCount += 1
            result.failureCodes.append("TRACE_FOOTER_MISMATCH")
        result.failureCodes = sorted(set(result.failureCodes))
        result.valid = not result.failureCodes
        return result
