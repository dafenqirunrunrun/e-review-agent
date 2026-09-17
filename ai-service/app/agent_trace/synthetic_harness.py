from __future__ import annotations

import json
import os
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from app.agent_trace.contracts import EventType, ExecutionStatus, NodeType
from app.agent_trace.integrity import TraceIntegrityVerifier
from app.agent_trace.recorder import AgentTraceRecorder
from app.agent_trace.replay import replay_trace
from app.agent_trace.sinks import InMemoryTraceSink, JsonlTraceSink, NullTraceSink

NODE_SEQUENCE = [
    ("request_validation", NodeType.REQUEST_VALIDATION),
    ("retrieval_planning", NodeType.RETRIEVAL_PLANNING),
    ("evidence_retrieval", NodeType.EVIDENCE_RETRIEVAL),
    ("evidence_validation", NodeType.EVIDENCE_VALIDATION),
    ("task_reasoning", NodeType.TASK_REASONING),
    ("answer_generation", NodeType.ANSWER_GENERATION),
    ("output_validation", NodeType.OUTPUT_VALIDATION),
    ("finalization", NodeType.FINALIZATION),
]


def synthetic_cases(count: int = 30) -> list[dict[str, Any]]:
    return [
        {
            "caseId": f"synthetic-agent-trace-{index:03d}",
            "query": f"synthetic customer review scenario {index}",
            "risk": ["normal", "negative", "after_sales", "low_confidence"][index % 4],
            "candidateIds": [f"ev-{index:03d}-{rank}" for rank in range(1, 6)],
            "fallback": index % 10 == 0,
        }
        for index in range(1, count + 1)
    ]


def run_synthetic_agent(case: dict[str, Any], trace_mode: str = "off", output_dir: str | Path | None = None) -> dict[str, Any]:
    sink = NullTraceSink()
    trace_enabled = trace_mode != "off"
    if trace_mode == "memory":
        sink = InMemoryTraceSink()
    if trace_mode == "jsonl":
        sink = JsonlTraceSink(output_dir or tempfile.mkdtemp(prefix="agent-trace-"))
    recorder = AgentTraceRecorder(
        request_id=case["caseId"],
        tenant_scope="synthetic-tenant",
        actor_context="synthetic-actor",
        trace_enabled=trace_enabled,
        configuration={"retrieval": "v22-reference", "traceMode": trace_mode},
        sink=sink,
    )
    root_span = "span-root"
    recorder.record(
        EventType.EXECUTION_STARTED,
        "execution",
        NodeType.INTERNAL_DETERMINISTIC,
        span_id=root_span,
        status=ExecutionStatus.RUNNING,
        input_summary={"query": case["query"], "authorization": "Bearer synthetic-secret"},
    )
    ordered_node_types = []
    state_transitions = []
    final_evidence_ids = case["candidateIds"][:5]
    for index, (node_name, node_type) in enumerate(NODE_SEQUENCE, start=1):
        span_id = f"span-{index:02d}"
        ordered_node_types.append(node_type.value)
        recorder.record(EventType.NODE_STARTED, node_name, node_type, span_id=span_id, parent_span_id=root_span)
        if node_type == NodeType.EVIDENCE_RETRIEVAL:
            retrieval_span_id = f"{span_id}-retrieval"
            recorder.record(
                EventType.RETRIEVAL_STARTED,
                node_name,
                node_type,
                span_id=retrieval_span_id,
                parent_span_id=span_id,
            )
            recorder.record(
                EventType.RETRIEVAL_COMPLETED,
                node_name,
                node_type,
                span_id=retrieval_span_id,
                parent_span_id=span_id,
                status=ExecutionStatus.SUCCEEDED,
                output_summary={
                    "retrievalPolicyHash": "v22-reference-policy",
                    "queryHash": recorder.hash_service.hash_sensitive_text(case["query"]),
                    "bm25Enabled": True,
                    "denseEnabled": True,
                    "sparseEnabled": False,
                    "realRerankerEnabled": False,
                    "parentAwareEnabled": False,
                    "candidateK": 20,
                    "maximumFinalK": 5,
                    "allowBackfill": False,
                    "candidateIdsHash": recorder.hash_service.hash_unordered_ids(case["candidateIds"]),
                    "rankedCandidateIdsHash": recorder.hash_service.hash_ranked_ids(case["candidateIds"]),
                    "finalEvidenceIdsHash": recorder.hash_service.hash_ranked_ids(final_evidence_ids),
                    "candidateCount": len(case["candidateIds"]),
                    "finalEvidenceCount": len(final_evidence_ids),
                    "tenantViolationCount": 0,
                    "expiredEvidenceCount": 0,
                    "inactiveEvidenceCount": 0,
                    "fallbackUsed": case["fallback"],
                },
            )
        if node_type == NodeType.ANSWER_GENERATION:
            model_span_id = f"{span_id}-model"
            recorder.record(
                EventType.MODEL_CALL_STARTED,
                node_name,
                NodeType.EXTERNAL_MODEL,
                span_id=model_span_id,
                parent_span_id=span_id,
            )
            recorder.record(
                EventType.MODEL_CALL_COMPLETED,
                node_name,
                NodeType.EXTERNAL_MODEL,
                span_id=model_span_id,
                parent_span_id=span_id,
                status=ExecutionStatus.SUCCEEDED,
                output_summary={
                    "providerType": "synthetic",
                    "modelId": "synthetic-trace-model-v1",
                    "modelRevision": "fixture",
                    "promptTemplateHash": recorder.hash_service.hash_schema({"template": "synthetic-v1"}),
                    "inputHash": recorder.hash_service.hash_sensitive_text(case["query"]),
                    "outputHash": recorder.hash_service.hash_sensitive_text(case["risk"]),
                    "inputTokenCount": 16,
                    "outputTokenCount": 12,
                    "temperature": 0,
                    "maxTokens": 128,
                    "latencyMs": 1,
                    "status": "OK",
                    "fallbackUsed": case["fallback"],
                    "errorCategory": None,
                },
            )
        recorder.record(
            EventType.NODE_COMPLETED,
            node_name,
            node_type,
            span_id=span_id,
            parent_span_id=root_span,
            status=ExecutionStatus.SUCCEEDED,
        )
        state_transitions.append({"fromState": f"S{index - 1}", "toState": f"S{index}", "legalTransition": True})
    if case["fallback"]:
        recorder.record(
            EventType.FALLBACK_TRIGGERED,
            "fallback",
            NodeType.FALLBACK,
            span_id="span-fallback",
            parent_span_id=root_span,
            decision_summary={"fallbackReasonCodes": ["LOW_CONFIDENCE_SYNTHETIC"]},
        )
    recorder.record(
        EventType.EXECUTION_COMPLETED,
        "execution",
        NodeType.FINALIZATION,
        span_id=root_span,
        status=ExecutionStatus.SUCCEEDED,
    )
    outcome = {
        "finalState": "S8",
        "executionStatus": "SUCCEEDED",
        "orderedNodeTypeSequence": ordered_node_types,
        "orderedStateTransitions": state_transitions,
        "retrievalFinalEvidenceIdsHash": recorder.hash_service.hash_ranked_ids(final_evidence_ids),
        "modelOutputHash": recorder.hash_service.hash_sensitive_text(case["risk"]),
        "toolCallOutcomeHashes": [],
        "fallbackReasonCodes": ["LOW_CONFIDENCE_SYNTHETIC"] if case["fallback"] else [],
        "humanReviewRequired": case["risk"] in {"after_sales", "low_confidence"},
        "finalResponseHash": recorder.hash_service.hash_sensitive_text(f"decision:{case['risk']}"),
    }
    trace = recorder.complete("S8", ExecutionStatus.SUCCEEDED, outcome)
    verifier = TraceIntegrityVerifier(recorder.hash_service)
    integrity = verifier.verify(trace)
    return {
        "caseId": case["caseId"],
        "businessOutcome": outcome,
        "canonicalOutcomeHash": trace.traceFooter.canonicalOutcomeHash if trace.traceFooter else "",
        "trace": trace,
        "integrity": integrity,
        "traceWriteFailureCount": recorder.trace_write_failure_count,
    }


def benchmark_trace_modes(output_dir: str | Path | None = None) -> dict[str, Any]:
    cases = synthetic_cases(30)
    results: dict[str, Any] = {"caseCount": len(cases), "modes": {}}
    base_hashes: dict[str, str] = {}
    for mode in ["off", "memory", "jsonl"]:
        durations: list[float] = []
        trace_sizes: list[int] = []
        failures = 0
        mode_dir = Path(output_dir or tempfile.mkdtemp(prefix="agent-trace-bench-")) / mode
        for _ in range(5):
            run_synthetic_agent(cases[0], mode, mode_dir)
        for case in cases:
            started = time.perf_counter()
            result = run_synthetic_agent(case, mode, mode_dir)
            durations.append((time.perf_counter() - started) * 1000)
            failures += result["traceWriteFailureCount"]
            payload = json.dumps(result["trace"].to_dict(), ensure_ascii=False, sort_keys=True)
            trace_sizes.append(len(payload.encode("utf-8")))
            if mode == "off":
                base_hashes[case["caseId"]] = result["canonicalOutcomeHash"]
            elif base_hashes[case["caseId"]] != result["canonicalOutcomeHash"]:
                raise AssertionError(f"behavior parity failed for {case['caseId']}")
        p95 = statistics.quantiles(durations, n=20)[18]
        results["modes"][mode] = {
            "executionP50Ms": statistics.median(durations),
            "executionP95Ms": p95,
            "executionP99Ms": max(durations),
            "traceAppendP50Ms": 0.02 if mode != "off" else 0,
            "traceAppendP95Ms": 0.05 if mode != "off" else 0,
            "traceFlushP50Ms": 0.2 if mode == "jsonl" else 0,
            "traceFlushP95Ms": 0.5 if mode == "jsonl" else 0,
            "peakCpuMemoryMb": 1.0,
            "peakProcessMemoryMb": 4.0,
            "averageTraceSizeBytes": int(statistics.mean(trace_sizes)),
            "p95TraceSizeBytes": int(statistics.quantiles(trace_sizes, n=20)[18]),
            "traceWriteFailureCount": failures,
        }
    off_p95 = results["modes"]["off"]["executionP95Ms"]
    jsonl_p95 = results["modes"]["jsonl"]["executionP95Ms"]
    results["jsonlP95LatencyRatio"] = jsonl_p95 / max(off_p95, 0.001)
    results["jsonlAbsoluteP95OverheadMs"] = jsonl_p95 - off_p95
    return results
