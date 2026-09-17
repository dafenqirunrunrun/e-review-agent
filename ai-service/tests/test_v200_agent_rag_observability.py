import logging
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.agent_rag.observability import GpuConcurrencyGate, GpuModelResidencyManager, metrics_registry, request_context, sanitize_log_fields
from app.agent_rag.phase3a_retrieval import make_bge_m3_provider
from app.main import app


client = TestClient(app)


def test_v200_observability_structured_logging_sanitizes_sensitive_fields(caplog):
    from app.agent_rag.observability import log_event

    caplog.set_level(logging.INFO, logger="agent_rag.runtime")
    with request_context(requestId="trace-1", tenantId="tenant-a", subjectId="review-1"):
        log_event("probe", token="secret-value", model_path=r"D:\EReviewAgent\models\bge-m3", errorMessage=r"C:\Users\demo\file.txt")

    text = caplog.text
    assert "trace-1" in text
    assert "secret-value" not in text
    assert r"D:\EReviewAgent\models" not in text
    assert "[redacted]" in text
    assert "[redacted-path]" in text


def test_v200_observability_header_body_trace_mismatch_is_rejected():
    payload = {
        "requestId": "body-id",
        "tenantId": "tenant-a",
        "subjectId": "review-1",
        "query": "broken product refund",
    }
    response = client.post("/api/v1/agent-rag/analyze", json=payload, headers={"X-Request-Id": "header-id"})
    assert response.status_code == 400
    assert response.json()["detail"] == "AGENT_RAG_REQUEST_ID_HEADER_MISMATCH"


def test_v200_observability_metrics_and_readiness_endpoints():
    metrics_registry.reset()
    payload = {
        "requestId": "metrics-id",
        "tenantId": "tenant-a",
        "subjectId": "review-2",
        "query": "broken product refund",
    }
    response = client.post("/api/v1/agent-rag/analyze", json=payload, headers={"X-Request-Id": "metrics-id"})
    assert response.status_code == 200

    live = client.get("/api/v1/internal/agent-rag/live").json()
    ready = client.get("/api/v1/internal/agent-rag/ready").json()
    metrics = client.get("/api/v1/internal/agent-rag/metrics").json()
    openmetrics = client.get("/api/v1/internal/agent-rag/metrics/openmetrics").text

    assert live["status"] == "live"
    assert ready["status"] in {"ready", "degraded"}
    assert metrics["metrics"]["counters"]["requests_total"] >= 1
    assert metrics["gpu"]["limit"] >= 1
    assert "resident_model" in metrics["residency"]
    assert "agent_rag_requests_total" in openmetrics


def test_v200_observability_gpu_gate_releases_slot_after_timeout():
    gate = GpuConcurrencyGate(limit=1, acquire_timeout_ms=25)
    with gate.acquire():
        with pytest.raises(TimeoutError, match="AGENT_RAG_GPU_QUEUE_TIMEOUT"):
            with gate.acquire():
                pass
    snapshot = gate.snapshot()
    assert snapshot.in_flight == 0
    assert snapshot.total_timeout == 1


def test_v200_observability_gpu_gate_serializes_concurrent_work():
    gate = GpuConcurrencyGate(limit=1, acquire_timeout_ms=1000)
    order = []

    def worker(name):
        with gate.acquire():
            order.append(name)
            time.sleep(0.02)

    first = threading.Thread(target=worker, args=("first",))
    second = threading.Thread(target=worker, args=("second",))
    first.start()
    second.start()
    first.join()
    second.join()

    assert order == ["first", "second"]
    assert gate.snapshot().in_flight == 0


def test_v22_gpu_residency_switches_models_and_calls_evictor():
    manager = GpuModelResidencyManager(mode="exclusive-model-slot")
    evicted = []
    with manager.acquire("embedding:bge-m3", unload_callback=lambda: evicted.append("embedding"), device="cuda"):
        assert manager.snapshot().resident_model == "embedding:bge-m3"
        assert manager.snapshot().active_requests == 1
    with manager.acquire("reranker:bge-reranker-v2-m3", unload_callback=lambda: evicted.append("reranker"), device="cuda"):
        assert manager.snapshot().resident_model == "reranker:bge-reranker-v2-m3"
    snapshot = manager.snapshot()
    assert evicted == ["embedding"]
    assert snapshot.active_requests == 0
    assert snapshot.model_load_count == 2
    assert snapshot.model_eviction_count == 1
    assert snapshot.model_switch_count == 1


def test_v200_observability_provider_factory_is_singleton_for_same_config():
    first = make_bge_m3_provider(provider_impl="legacy-cls", model_path="__missing__", device="cpu")
    second = make_bge_m3_provider(provider_impl="legacy-cls", model_path="__missing__", device="cpu")
    different = make_bge_m3_provider(provider_impl="flagembedding", model_path="__missing__", device="cpu")

    assert first is second
    assert first is not different


def test_v200_observability_sanitize_log_fields_recurses_without_raw_paths():
    payload = sanitize_log_fields({"nested": {"authorization": "Bearer token", "path": r"C:\private\model"}})
    assert payload["nested"]["authorization"] == "[redacted]"
    assert payload["nested"]["path"] == "[redacted-path]"
