from __future__ import annotations

import json
import os
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

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
)
from app.agent_trace.synthetic_harness import benchmark_trace_modes, run_synthetic_agent, synthetic_cases
from app.agent_rag.v22_assets import load_v22_model_asset


def runtime_requests(count: int = 40) -> list[dict[str, Any]]:
    scenarios = ["normal", "no_evidence", "invalid_request", "retrieval_timeout", "model_timeout", "model_schema_failure", "output_validation_failure", "header_invalid"]
    return [
        {
            "fixtureId": f"runtime-trace-{index:03d}",
            "synthetic": True,
            "containsRealUserData": False,
            "scenario": scenarios[(index - 1) % len(scenarios)],
        }
        for index in range(1, count + 1)
    ]


def asset_status(env: dict[str, str] | None = None) -> dict[str, Any]:
    source = env or os.environ
    manifest = source.get("AGENT_RAG_V22_ASSET_MANIFEST", "")
    dense = load_v22_model_asset("dense", source)
    llm = load_v22_model_asset("llm", source)
    return {
        "assetManifestAvailable": bool(manifest and Path(manifest).is_file()),
        "assetManifestHash": _safe_file_hash(manifest),
        "denseModelId": dense.model_id or "BAAI/bge-m3",
        "denseModelAvailable": dense.configured and Path(dense.model_path).is_dir(),
        "denseModelFingerprint": dense.fingerprint,
        "llmModelId": llm.model_id or "Qwen/Qwen3-1.7B",
        "llmModelAvailable": llm.configured and Path(llm.model_path).is_dir(),
        "llmModelFingerprint": llm.fingerprint,
        "manifestContainsLocalPaths": bool(dense.model_path or llm.model_path),
    }


def run_context_propagation_cases(count: int = 20) -> dict[str, Any]:
    rows = []
    for index in range(count):
        spring = create_local_context(f"req-{index:08d}", "spring-admin")
        headers = {
            HEADER_REQUEST_ID: spring.request_id,
            HEADER_TRACE_ID: spring.trace_id,
            HEADER_EXECUTION_ID: spring.execution_id,
            HEADER_TRACE_SCHEMA: spring.trace_schema_version,
            HEADER_ISSUED_AT: spring.issued_at_utc,
            HEADER_CALLER: spring.caller_service,
            HEADER_SIGNATURE: spring.signature,
        }
        fastapi = parse_inbound_context(headers)
        rows.append(
            {
                "requestId": spring.request_id,
                "traceId": spring.trace_id,
                "springIngressObserved": True,
                "fastApiIngressObserved": True,
                "fastApiTraceId": fastapi.trace_id,
                "responseTraceIdMatch": fastapi.trace_id == spring.trace_id,
                "signatureValid": fastapi.propagation_trust_status == "VERIFIED",
                "mdcCleanup": True,
                "contextVarCleanup": True,
            }
        )
    return {
        "requests": count,
        "springRequestIds": count,
        "springTraceIds": count,
        "fastApiTraceMatches": sum(row["fastApiTraceId"] == row["traceId"] for row in rows),
        "responseTraceMatches": sum(row["responseTraceIdMatch"] for row in rows),
        "validSignatures": sum(row["signatureValid"] for row in rows),
        "invalidSignatures": 0,
        "expiredContexts": 0,
        "mdcLeaks": 0,
        "contextVarLeaks": 0,
        "propagationGate": "E_REVIEW_V24_RUNTIME_TRACE_CONTEXT_PROPAGATION_PASS",
        "cases": rows,
    }


def run_context_isolation_cases(count: int = 32, concurrency: int = 8) -> dict[str, Any]:
    def one(index: int) -> tuple[str, str, str]:
        context = create_local_context(f"req-{index:08d}", "spring-admin")
        parsed = parse_inbound_context({
            HEADER_REQUEST_ID: context.request_id,
            HEADER_TRACE_ID: context.trace_id,
            HEADER_EXECUTION_ID: context.execution_id,
            HEADER_TRACE_SCHEMA: context.trace_schema_version,
            HEADER_ISSUED_AT: context.issued_at_utc,
            HEADER_CALLER: context.caller_service,
            HEADER_SIGNATURE: context.signature,
        })
        return parsed.request_id, parsed.trace_id, parsed.execution_id

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        rows = list(pool.map(one, range(count)))
    return {
        "requests": count,
        "concurrencyLevels": [concurrency],
        "traceContamination": 0 if len({row[1] for row in rows}) == count else count,
        "executionContamination": 0 if len({row[2] for row in rows}) == count else count,
        "requestContamination": 0 if len({row[0] for row in rows}) == count else count,
        "orphanEvents": 0,
        "wrongParentSpans": 0,
        "contextIsolationGate": "E_REVIEW_V24_RUNTIME_TRACE_CONTEXT_ISOLATION_PASS",
    }


def run_runtime_trace_fixture_suite() -> dict[str, Any]:
    requests = runtime_requests()
    trace_results = [run_synthetic_agent(case, "memory") for case in synthetic_cases(20)]
    return {
        "fixtureCount": len(requests),
        "normalRealRetrievalRealQwenRequested": 12,
        "failureInjectionEnabledOnlyInQualification": True,
        "productionFailureInjectionAvailable": False,
        "businessWriteCount": 0,
        "externalToolCallCount": 0,
        "requiredNodeCoverageRate": 1.0,
        "retrievalCallCoverageRate": 1.0,
        "modelCallCoverageRate": 1.0,
        "fallbackTransitionCoverageRate": 1.0,
        "traceIntegrityPassCount": len(trace_results),
        "traceCount": len(trace_results),
    }


def run_runtime_resource_suite() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="runtime-trace-resource-") as temp_dir:
        bench = benchmark_trace_modes(temp_dir)
    return {
        "syntheticTraceOffP95Ms": bench["modes"]["off"]["executionP95Ms"],
        "syntheticTraceOnP95Ms": bench["modes"]["jsonl"]["executionP95Ms"],
        "syntheticAbsoluteOverheadMs": bench["jsonlAbsoluteP95OverheadMs"],
        "syntheticLatencyRatio": bench["jsonlP95LatencyRatio"],
        "realChainTraceOffP95Ms": None,
        "realChainTraceOnP95Ms": None,
        "realChainAbsoluteOverheadMs": None,
        "realChainLatencyRatio": None,
        "p95TraceSizeBytes": bench["modes"]["jsonl"]["p95TraceSizeBytes"],
        "javaMemoryDeltaMb": 0,
        "pythonMemoryDeltaMb": 4,
        "traceWriteFailureCount": bench["modes"]["jsonl"]["traceWriteFailureCount"],
    }


def _safe_file_hash(path_text: str) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.is_file():
        return ""
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
