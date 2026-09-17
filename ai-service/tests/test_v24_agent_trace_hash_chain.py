from __future__ import annotations

from copy import deepcopy

from app.agent_trace.integrity import TraceIntegrityVerifier
from app.agent_trace.synthetic_harness import run_synthetic_agent, synthetic_cases


def test_hash_chain_and_footer_verify() -> None:
    result = run_synthetic_agent(synthetic_cases(1)[0], "memory")
    integrity = result["integrity"]
    assert integrity.valid is True
    assert integrity.sequenceGapCount == 0
    assert integrity.hashChainFailureCount == 0
    assert integrity.traceFooterMismatchCount == 0


def test_tamper_detection_for_modify_delete_insert_and_reorder() -> None:
    result = run_synthetic_agent(synthetic_cases(1)[0], "memory")
    trace = result["trace"]
    verifier = TraceIntegrityVerifier(result["trace"].events and result["trace"].events[0] and result["trace"].events[0] and __import__("app.agent_trace.hash_service", fromlist=["TraceHashService"]).TraceHashService("synthetic-qualification-key"))

    modified = deepcopy(trace)
    modified.events[1].nodeName = "tampered"
    assert "EVENT_HASH_MISMATCH" in verifier.verify(modified).failureCodes

    deleted = deepcopy(trace)
    deleted.events.pop(2)
    deletion_codes = verifier.verify(deleted).failureCodes
    assert "SEQUENCE_NUMBER_GAP" in deletion_codes or "TRACE_FOOTER_MISMATCH" in deletion_codes

    inserted = deepcopy(trace)
    inserted.events.insert(1, deepcopy(trace.events[1]))
    insertion_codes = verifier.verify(inserted).failureCodes
    assert "EVENT_INSERTION_DETECTED" in insertion_codes or "SEQUENCE_NUMBER_GAP" in insertion_codes

    reordered = deepcopy(trace)
    reordered.events[1], reordered.events[2] = reordered.events[2], reordered.events[1]
    reorder_codes = verifier.verify(reordered).failureCodes
    assert "PREVIOUS_HASH_MISMATCH" in reorder_codes or "SEQUENCE_NUMBER_GAP" in reorder_codes
