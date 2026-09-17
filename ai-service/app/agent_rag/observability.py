from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import threading
import time
from collections import defaultdict
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import Any, Callable, Iterator


_REQUEST_CONTEXT: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar("agent_rag_request_context", default={})
_LOGGER = logging.getLogger("agent_rag.runtime")
_PATH_PATTERN = re.compile(r"([A-Za-z]:\\[^\s\"']+)|((?<![A-Za-z0-9_])/(?:home|Users|mnt|var|tmp|opt)/[^\s\"']+)")
_SENSITIVE_KEYS = ("authorization", "token", "secret", "password", "api_key", "model_path", "prompt")


def current_context() -> dict[str, str]:
    return dict(_REQUEST_CONTEXT.get())


@contextmanager
def request_context(**fields: str) -> Iterator[None]:
    clean = {key: sanitize_log_value(value) for key, value in fields.items() if value is not None and str(value)}
    token = _REQUEST_CONTEXT.set(clean)
    try:
        yield
    finally:
        _REQUEST_CONTEXT.reset(token)


def sanitize_log_value(value: Any) -> str:
    text = str(value)
    text = _PATH_PATTERN.sub("[redacted-path]", text)
    return text[:240]


def sanitize_log_fields(fields: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in fields.items():
        lower = key.lower()
        if any(name in lower for name in _SENSITIVE_KEYS):
            safe[key] = "[redacted]"
        elif isinstance(value, dict):
            safe[key] = sanitize_log_fields(value)
        elif isinstance(value, list):
            safe[key] = [sanitize_log_value(item) if not isinstance(item, dict) else sanitize_log_fields(item) for item in value[:20]]
        elif isinstance(value, str):
            safe[key] = sanitize_log_value(value)
        else:
            safe[key] = value
    return safe


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **current_context(), **sanitize_log_fields(fields)}
    if os.getenv("AGENT_RAG_LOG_FORMAT", "json").lower() == "json":
        _LOGGER.info(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        _LOGGER.info(" ".join(f"{key}={value}" for key, value in payload.items()))


class AgentRagMetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._gauges: dict[str, float] = {}

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._histograms.clear()
            self._gauges.clear()

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] += amount

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            values = self._histograms[name]
            values.append(float(value))
            if len(values) > 2048:
                del values[: len(values) - 2048]

    def gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = float(value)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            histograms = {}
            for name, values in self._histograms.items():
                ordered = sorted(values)
                histograms[name] = {
                    "count": len(ordered),
                    "min": ordered[0] if ordered else 0,
                    "max": ordered[-1] if ordered else 0,
                    "p95": _percentile(ordered, 0.95),
                }
            return {
                "counters": dict(self._counters),
                "histograms": histograms,
                "gauges": dict(self._gauges),
            }

    def openmetrics(self) -> str:
        snapshot = self.snapshot()
        lines: list[str] = []
        for name, value in sorted(snapshot["counters"].items()):
            lines.append(f"agent_rag_{name} {value}")
        for name, value in sorted(snapshot["gauges"].items()):
            lines.append(f"agent_rag_{name} {value}")
        for name, values in sorted(snapshot["histograms"].items()):
            lines.append(f"agent_rag_{name}_count {values['count']}")
            lines.append(f"agent_rag_{name}_p95 {values['p95']}")
        return "\n".join(lines) + "\n"


metrics_registry = AgentRagMetricsRegistry()


@dataclass
class GpuGateSnapshot:
    limit: int
    in_flight: int
    waiting: int
    acquire_timeout_ms: int
    total_acquired: int
    total_timeout: int


@dataclass
class GpuResidencySnapshot:
    mode: str
    resident_model: str
    active_requests: int
    queue_depth: int
    model_load_count: int
    model_eviction_count: int
    model_switch_count: int
    oom_count: int
    cuda_allocated_mb: float
    cuda_reserved_mb: float
    cuda_free_mb: float
    cuda_peak_mb: float


class GpuConcurrencyGate:
    def __init__(self, *, limit: int = 1, acquire_timeout_ms: int = 2000) -> None:
        self.limit = max(1, int(limit))
        self.acquire_timeout_ms = max(1, int(acquire_timeout_ms))
        self._condition = threading.Condition()
        self._in_flight = 0
        self._waiting = 0
        self._total_acquired = 0
        self._total_timeout = 0

    @contextmanager
    def acquire(self) -> Iterator[None]:
        deadline = time.monotonic() + self.acquire_timeout_ms / 1000.0
        with self._condition:
            self._waiting += 1
            try:
                while self._in_flight >= self.limit:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        self._total_timeout += 1
                        metrics_registry.increment("gpu_queue_timeout_total")
                        raise TimeoutError("AGENT_RAG_GPU_QUEUE_TIMEOUT")
                    self._condition.wait(timeout=remaining)
                self._waiting -= 1
                self._in_flight += 1
                self._total_acquired += 1
                metrics_registry.gauge("gpu_in_flight", self._in_flight)
            except Exception:
                if self._waiting > 0:
                    self._waiting -= 1
                raise
        try:
            yield
        finally:
            with self._condition:
                self._in_flight = max(0, self._in_flight - 1)
                metrics_registry.gauge("gpu_in_flight", self._in_flight)
                self._condition.notify()

    def snapshot(self) -> GpuGateSnapshot:
        with self._condition:
            return GpuGateSnapshot(
                limit=self.limit,
                in_flight=self._in_flight,
                waiting=self._waiting,
                acquire_timeout_ms=self.acquire_timeout_ms,
                total_acquired=self._total_acquired,
                total_timeout=self._total_timeout,
            )


gpu_gate = GpuConcurrencyGate(
    limit=int(os.getenv("AGENT_RAG_GPU_CONCURRENCY", "1")),
    acquire_timeout_ms=int(os.getenv("AGENT_RAG_GPU_QUEUE_TIMEOUT_MS", "2000")),
)


class GpuModelResidencyManager:
    def __init__(self, *, mode: str = "disabled") -> None:
        self.mode = mode
        self._condition = threading.Condition()
        self._resident_model = ""
        self._active_requests = 0
        self._model_load_count = 0
        self._model_eviction_count = 0
        self._model_switch_count = 0
        self._oom_count = 0
        self._evictors: dict[str, Callable[[], None]] = {}

    @contextmanager
    def acquire(self, model_key: str, *, unload_callback: Callable[[], None] | None = None, device: str = "cuda") -> Iterator[None]:
        if self.mode != "exclusive-model-slot" or device != "cuda":
            yield
            return
        with gpu_gate.acquire():
            self._enter_model(model_key, unload_callback)
            try:
                yield
            except Exception as exc:
                if "out of memory" in str(exc).lower():
                    self.record_oom()
                raise
            finally:
                self._leave_model()

    def _enter_model(self, model_key: str, unload_callback: Callable[[], None] | None) -> None:
        evictor: Callable[[], None] | None = None
        with self._condition:
            while self._active_requests > 0:
                self._condition.wait(timeout=0.05)
            if unload_callback is not None:
                self._evictors[model_key] = unload_callback
            if self._resident_model != model_key:
                if self._resident_model:
                    evictor = self._evictors.get(self._resident_model)
                    self._model_eviction_count += 1
                    self._model_switch_count += 1
                self._resident_model = model_key
                self._model_load_count += 1
            self._active_requests += 1
            self._publish_metrics()
        if evictor is not None:
            try:
                evictor()
            finally:
                _release_cuda_cache()

    def _leave_model(self) -> None:
        with self._condition:
            self._active_requests = max(0, self._active_requests - 1)
            self._publish_metrics()
            self._condition.notify_all()

    def record_oom(self) -> None:
        with self._condition:
            self._oom_count += 1
            self._publish_metrics()

    def snapshot(self) -> GpuResidencySnapshot:
        cuda = _cuda_snapshot()
        gate = gpu_gate.snapshot()
        with self._condition:
            return GpuResidencySnapshot(
                mode=self.mode,
                resident_model=self._resident_model,
                active_requests=self._active_requests,
                queue_depth=gate.waiting,
                model_load_count=self._model_load_count,
                model_eviction_count=self._model_eviction_count,
                model_switch_count=self._model_switch_count,
                oom_count=self._oom_count,
                cuda_allocated_mb=cuda["allocated"],
                cuda_reserved_mb=cuda["reserved"],
                cuda_free_mb=cuda["free"],
                cuda_peak_mb=cuda["peak"],
            )

    def _publish_metrics(self) -> None:
        metrics_registry.gauge("gpu_residency_active_requests", self._active_requests)
        metrics_registry.gauge("gpu_residency_model_load_count", self._model_load_count)
        metrics_registry.gauge("gpu_residency_model_eviction_count", self._model_eviction_count)
        metrics_registry.gauge("gpu_residency_model_switch_count", self._model_switch_count)
        metrics_registry.gauge("gpu_residency_oom_count", self._oom_count)


model_residency = GpuModelResidencyManager(
    mode=os.getenv("AGENT_MODEL_RESIDENCY_MODE", "disabled").strip().lower() or "disabled"
)


def model_residency_snapshot() -> dict[str, Any]:
    return model_residency.snapshot().__dict__


def _release_cuda_cache() -> None:
    try:
        import gc
        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except Exception:
        return None


def _cuda_snapshot() -> dict[str, float]:
    try:
        import torch

        if not torch.cuda.is_available():
            return {"allocated": 0.0, "reserved": 0.0, "free": 0.0, "peak": 0.0}
        free, _total = torch.cuda.mem_get_info()
        return {
            "allocated": round(torch.cuda.memory_allocated(0) / 1024 / 1024, 2),
            "reserved": round(torch.cuda.memory_reserved(0) / 1024 / 1024, 2),
            "free": round(free / 1024 / 1024, 2),
            "peak": round(torch.cuda.max_memory_reserved(0) / 1024 / 1024, 2),
        }
    except Exception:
        return {"allocated": 0.0, "reserved": 0.0, "free": 0.0, "peak": 0.0}


def _noop_context() -> Iterator[None]:
    return nullcontext()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    index = int(round((len(values) - 1) * percentile))
    return values[max(0, min(index, len(values) - 1))]
