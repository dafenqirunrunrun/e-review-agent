from __future__ import annotations

"""Measure Langfuse sidecar overhead with matched fresh-process HTTP workloads."""

import argparse
import json
import math
import os
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts/langfuse/on_off_performance.json"
WORKLOADS = ("light", "strict_uncached", "strict_cached")
TAIL_BUDGETS = {
    "light": {"p95Percent": 25.0, "p95AbsoluteMs": 20.0, "p99Percent": 35.0, "p99AbsoluteMs": 30.0},
    "strict_uncached": {"p95Percent": 25.0, "p95AbsoluteMs": 100.0, "p99Percent": 35.0, "p99AbsoluteMs": 150.0},
    "strict_cached": {"p95Percent": 25.0, "p95AbsoluteMs": 20.0, "p99Percent": 35.0, "p99AbsoluteMs": 30.0},
}


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * ratio) - 1))
    return round(ordered[index], 2)


def latency_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0, "avg": 0.0}
    return {
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": round(max(values), 2),
        "avg": round(statistics.mean(values), 2),
    }


def overhead(on_value: float, off_value: float) -> dict[str, float]:
    delta = round(on_value - off_value, 2)
    percent = round(delta / off_value * 100, 2) if off_value > 0 else 0.0
    return {"deltaMs": delta, "deltaPercent": percent}


def tail_gate(workload: str, off: dict[str, Any], on: dict[str, Any]) -> dict[str, Any]:
    budget = TAIL_BUDGETS[workload]
    p95 = overhead(on["wallLatencyMs"]["p95"], off["wallLatencyMs"]["p95"])
    p99 = overhead(on["wallLatencyMs"]["p99"], off["wallLatencyMs"]["p99"])
    p95_allowed = max(budget["p95AbsoluteMs"], off["wallLatencyMs"]["p95"] * budget["p95Percent"] / 100)
    p99_allowed = max(budget["p99AbsoluteMs"], off["wallLatencyMs"]["p99"] * budget["p99Percent"] / 100)
    passed = p95["deltaMs"] <= p95_allowed and p99["deltaMs"] <= p99_allowed
    return {
        "p95": p95,
        "p99": p99,
        "allowedP95DeltaMs": round(p95_allowed, 2),
        "allowedP99DeltaMs": round(p99_allowed, 2),
        "status": "PASS" if passed else "FAIL",
    }


def _request(url: str, payload: dict[str, Any], timeout: float = 120.0) -> tuple[dict[str, Any], float, str, bool]:
    started = time.perf_counter()
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            return body, round((time.perf_counter() - started) * 1000, 2), "", False
    except Exception as exc:
        timed_out = isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)
        return {}, round((time.perf_counter() - started) * 1000, 2), type(exc).__name__, timed_out


def _get_json(url: str, timeout: float = 10.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _payload(review_id: str, text: str, rating: int) -> dict[str, Any]:
    return {
        "reviewId": review_id,
        "productId": "STEP211-PERF",
        "productName": "Step 21.1 performance fixture",
        "reviewText": text,
        "imageUrls": [],
        "rating": rating,
    }


def _decision_signature(body: dict[str, Any]) -> dict[str, Any]:
    contract = body.get("review_governance") or {}
    return {
        "riskTypes": contract.get("riskTypes") or body.get("risk_types") or [],
        "route": ((body.get("extra") or {}).get("agentic") or {}).get("route"),
        "decision": (contract.get("decision") or {}).get("code") or body.get("route_decision"),
        "reflection": contract.get("evidenceStatus") or body.get("evidence_status"),
        "requiresHumanReview": contract.get("requiresHumanReview", body.get("requires_human_review")),
    }


def _workflow_latency(body: dict[str, Any]) -> float:
    return float((((body.get("extra") or {}).get("latencyBreakdown") or {}).get("totalMs") or 0.0))


def _embedding_latency(body: dict[str, Any]) -> float:
    return float((((body.get("extra") or {}).get("latencyBreakdown") or {}).get("embeddingComputeMs") or 0.0))


def _actual_mode(body: dict[str, Any]) -> str:
    return str((((body.get("extra") or {}).get("policyRetrieval") or {}).get("actualMode") or "not_required"))


def _wait_for_service(base_url: str, process: subprocess.Popen[Any], timeout_seconds: int = 180) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    error = ""
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"PERF_SERVICE_EXITED:{process.returncode}")
        try:
            return _get_json(base_url + "/api/v1/system/readiness")
        except Exception as exc:
            error = type(exc).__name__
            time.sleep(0.5)
    raise RuntimeError(f"PERF_SERVICE_START_TIMEOUT:{error}")


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _start_service(port: int, enabled: bool, run_token: str, log_path: Path) -> tuple[subprocess.Popen[Any], Any]:
    env = os.environ.copy()
    env.update(
        {
            "LANGFUSE_ENABLED": "true" if enabled else "false",
            "LANGFUSE_RELEASE": f"step21.1-perf-{run_token}",
            "E_REVIEW_AGENTIC_WORKFLOW_ENABLED": "true",
            "E_REVIEW_AGENTIC_CHECKPOINT_ENABLED": "false",
            "E_REVIEW_POLICY_RAG_DENSE_RETRIEVAL_ENABLED": "true",
            "E_REVIEW_POLICY_RAG_QUERY_CACHE_ENABLED": "true",
            "E_REVIEW_POLICY_RAG_EMBEDDING_MAX_CONCURRENCY": "1",
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
        }
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("w", encoding="utf-8")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    return process, log_handle


def _stop_service(process: subprocess.Popen[Any], log_handle: Any) -> None:
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    finally:
        log_handle.close()


def _run_one(base_url: str, review_id: str, text: str, rating: int) -> dict[str, Any]:
    body, wall_ms, error, timed_out = _request(base_url + "/api/v1/review/analyze", _payload(review_id, text, rating))
    return {
        "reviewId": review_id,
        "wallMs": wall_ms,
        "workflowMs": _workflow_latency(body),
        "embeddingMs": _embedding_latency(body),
        "actualMode": _actual_mode(body),
        "signature": _decision_signature(body),
        "error": error,
        "timeout": timed_out,
    }


def _summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [sample for sample in samples if not sample["error"]]
    count = len(samples)
    return {
        "requestCount": count,
        "wallLatencyMs": latency_summary([sample["wallMs"] for sample in successful]),
        "workflowLatencyMs": latency_summary([sample["workflowMs"] for sample in successful]),
        "errorRate": round((count - len(successful)) / max(1, count), 4),
        "timeoutRate": round(sum(sample["timeout"] for sample in samples) / max(1, count), 4),
        "embeddingCacheHitProxyRate": round(sum(sample["embeddingMs"] == 0 for sample in successful) / max(1, len(successful)), 4),
        "actualModes": dict(sorted(Counter(sample["actualMode"] for sample in successful).items())),
        "signatures": [sample["signature"] for sample in successful],
        "errors": dict(sorted(Counter(sample["error"] for sample in samples if sample["error"]).items())),
    }


def _warmup(base_url: str, marker: str) -> list[str]:
    ids: list[str] = []
    warmups = [
        ("provider", "五星截图返现，并要求删除差评。", 5),
        ("light-1", "物流很快，包装完整，商品和描述一致。", 5),
        ("light-2", "物流很快，包装完整，商品和描述一致。", 5),
        ("uncached-1", "五星截图返现并要求删除差评。预热编号 A", 5),
        ("uncached-2", "五星截图返现并要求删除差评。预热编号 B", 5),
        ("cached-prime", "五星截图返现，并要求删除差评。固定缓存查询", 5),
        ("cached-hit", "五星截图返现，并要求删除差评。固定缓存查询", 5),
    ]
    for suffix, text, rating in warmups:
        review_id = f"{marker}-warm-{suffix}"
        sample = _run_one(base_url, review_id, text, rating)
        if sample["error"]:
            raise RuntimeError(f"PERF_WARMUP_FAILED:{suffix}:{sample['error']}")
        ids.append(review_id)
    return ids


def _run_workloads(base_url: str, marker: str, samples_per_workload: int) -> tuple[dict[str, Any], list[str]]:
    all_ids: list[str] = []
    result: dict[str, Any] = {}
    definitions = {
        "light": [("物流很快，包装完整，商品和描述一致。", 5) for _ in range(samples_per_workload)],
        "strict_uncached": [
            (f"五星截图返现并要求删除差评。性能样本编号 {index:03d}", 5)
            for index in range(samples_per_workload)
        ],
        "strict_cached": [("五星截图返现，并要求删除差评。固定缓存查询", 5) for _ in range(samples_per_workload)],
    }
    for workload in WORKLOADS:
        samples: list[dict[str, Any]] = []
        for index, (text, rating) in enumerate(definitions[workload], start=1):
            review_id = f"{marker}-{workload}-{index:03d}"
            samples.append(_run_one(base_url, review_id, text, rating))
            all_ids.append(review_id)
        result[workload] = _summarize(samples)
    return result, all_ids


def _clickhouse_export_count(marker: str) -> int | None:
    safe_marker = "".join(char for char in marker if char.isalnum() or char in "-_")
    query = (
        "SELECT uniqExact(trace_id) FROM default.events_full "
        "WHERE name='review_governance_analysis' AND "
        f"arrayElement(metadata_values,indexOf(metadata_names,'reviewId')) LIKE '{safe_marker}%'"
    )
    try:
        output = subprocess.check_output(
            ["docker", "exec", "langfuse-clickhouse-1", "clickhouse-client", "--query", query],
            text=True,
            encoding="utf-8",
            timeout=15,
        )
        return int(output.strip())
    except Exception:
        return None


def _wait_for_exports(marker: str, expected: int, timeout_seconds: int = 30) -> int | None:
    deadline = time.time() + timeout_seconds
    latest: int | None = None
    while time.time() < deadline:
        latest = _clickhouse_export_count(marker)
        if latest is not None and latest >= expected:
            return latest
        time.sleep(2)
    return latest


def run_condition(enabled: bool, port: int, run_token: str, samples: int, output_dir: Path) -> dict[str, Any]:
    label = "on" if enabled else "off"
    marker = f"step211perf-{run_token}-{label}"
    process, log_handle = _start_service(port, enabled, run_token, output_dir / f"service-{label}.log")
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_service(base_url, process)
        warmup_ids = _warmup(base_url, marker)
        readiness = _get_json(base_url + "/api/v1/system/readiness")
        provider = readiness["policyRag"]["dense"]["providerMetrics"]
        if (
            readiness["policyRag"].get("retrievalMode") != "hybrid"
            or readiness["policyRag"]["dense"].get("providerStatus") != "ready"
            or provider.get("modelLoadCount") != 1
        ):
            raise RuntimeError("PERF_WARM_RUNTIME_NOT_READY")
        workloads, formal_ids = _run_workloads(base_url, marker, samples)
        total_requests = len(warmup_ids) + len(formal_ids)
        exported = _wait_for_exports(marker, total_requests) if enabled else 0
        return {
            "langfuseEnabled": enabled,
            "marker": marker,
            "warmupRequestCount": len(warmup_ids),
            "formalRequestCount": len(formal_ids),
            "runtime": {
                "retrievalMode": readiness["policyRag"].get("retrievalMode"),
                "providerStatus": readiness["policyRag"]["dense"].get("providerStatus"),
                "modelLoadCount": provider.get("modelLoadCount"),
                "embeddingConcurrency": provider.get("embeddingGate", {}).get("maxConcurrency"),
                "policyChunkCount": readiness["policyRag"].get("chunkCount"),
            },
            "workloads": workloads,
            "telemetry": {
                "expectedTraceCount": total_requests if enabled else 0,
                "exportedTraceCount": exported,
                "exportFailureCount": None if enabled and exported is None else max(0, total_requests - int(exported or 0)) if enabled else 0,
                "flushLatencyMs": None,
                "flushPolicy": "background export; reconciliation at group end; no per-request flush",
            },
        }
    finally:
        _stop_service(process, log_handle)


def compare_conditions(off: dict[str, Any], on: dict[str, Any]) -> dict[str, Any]:
    workloads: dict[str, Any] = {}
    decision_mismatches = 0
    for workload in WORKLOADS:
        off_workload = off["workloads"][workload]
        on_workload = on["workloads"][workload]
        mismatches = sum(left != right for left, right in zip(off_workload["signatures"], on_workload["signatures"]))
        decision_mismatches += mismatches
        workloads[workload] = {**tail_gate(workload, off_workload, on_workload), "decisionMismatches": mismatches}
    all_workloads_pass = all(value["status"] == "PASS" for value in workloads.values())
    zero_runtime_errors = all(
        condition["workloads"][workload][metric] == 0
        for condition in (off, on)
        for workload in WORKLOADS
        for metric in ("errorRate", "timeoutRate")
    )
    export_failures = on["telemetry"].get("exportFailureCount")
    passed = all_workloads_pass and zero_runtime_errors and decision_mismatches == 0 and export_failures == 0
    return {
        "workloads": workloads,
        "decisionMismatches": decision_mismatches,
        "zeroRuntimeErrors": zero_runtime_errors,
        "telemetryDeliveryComplete": export_failures == 0,
        "gate": "PASS" if passed else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Step 21.1 Langfuse ON/OFF performance benchmark.")
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--port", type=int, default=8018)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--order", choices=("off-on", "on-off"), default="off-on")
    args = parser.parse_args()
    if args.samples < 30:
        raise SystemExit("PERF_SAMPLE_COUNT_MUST_BE_AT_LEAST_30")
    if not _port_available(args.port):
        raise SystemExit(f"PERF_PORT_IN_USE:{args.port}")

    run_token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output.resolve()
    output_dir = output.parent / f"performance-{run_token}"
    started = time.perf_counter()
    if args.order == "off-on":
        off = run_condition(False, args.port, run_token, args.samples, output_dir)
        on = run_condition(True, args.port, run_token, args.samples, output_dir)
    else:
        on = run_condition(True, args.port, run_token, args.samples, output_dir)
        off = run_condition(False, args.port, run_token, args.samples, output_dir)
    comparison = compare_conditions(off, on)
    report = {
        "schemaVersion": "step21-1-langfuse-performance-v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "runToken": run_token,
        "samplesPerWorkload": args.samples,
        "conditionOrder": args.order,
        "processDesign": "matched fresh processes on one machine; only LANGFUSE_ENABLED differs",
        "tailBudgets": TAIL_BUDGETS,
        "off": off,
        "on": on,
        "comparison": comparison,
        "durationSeconds": round(time.perf_counter() - started, 2),
        "gate": comparison["gate"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    printable = json.loads(json.dumps(report))
    for condition in ("off", "on"):
        printable[condition].pop("marker", None)
        for workload in WORKLOADS:
            printable[condition]["workloads"][workload].pop("signatures", None)
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    return 0 if report["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
