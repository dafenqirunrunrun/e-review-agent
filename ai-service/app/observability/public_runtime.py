from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from threading import Lock


REQUEST_ID_HEADER = "X-Request-ID"


@dataclass
class AiPublicRuntimeMetrics:
    http_request_total: int = 0
    http_error_total: int = 0
    http_duration_ms_total: int = 0
    ai_analysis_total: int = 0
    ai_analysis_failure_total: int = 0
    last_request_id: str | None = None


_metrics = AiPublicRuntimeMetrics()
_lock = Lock()
logger = logging.getLogger("e_review.public_runtime")


def record_http(request_id: str, operation: str, status: int, duration_ms: int) -> None:
    with _lock:
        _metrics.http_request_total += 1
        _metrics.http_duration_ms_total += max(0, duration_ms)
        if status >= 500:
            _metrics.http_error_total += 1
        _metrics.last_request_id = request_id
    logger.info(json.dumps({
        "timestamp": int(time.time() * 1000),
        "level": "INFO",
        "service": "ai-service",
        "request_id": request_id,
        "operation": operation,
        "status": status,
        "duration_ms": duration_ms,
    }, ensure_ascii=False))


def record_ai_analysis(request_id: str, success: bool) -> None:
    with _lock:
        _metrics.ai_analysis_total += 1
        if not success:
            _metrics.ai_analysis_failure_total += 1
        _metrics.last_request_id = request_id


def snapshot() -> dict:
    with _lock:
        return asdict(_metrics)
