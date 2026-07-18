from __future__ import annotations

import json
import time
import urllib.request

from public_business_smoke import _admin_headers, _admin_token
from public_runtime_common import PublicRuntimeError, ai_url, assert_litemall_ok, backend_url, main_guard, request_json, write_evidence


def _request_with_headers(method: str, url: str, request_id: str) -> tuple[int, dict, dict]:
    req = urllib.request.Request(url, method=method, headers={"X-Request-ID": request_id, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, dict(response.headers), json.loads(body) if body else {}


def main() -> None:
    evidence: dict = {}
    request_id = "public-ops-observability-" + str(int(time.time()))

    backend_status, backend_headers, backend_ready = _request_with_headers("GET", backend_url() + "/public/runtime/ready", request_id)
    if backend_status != 200 or backend_headers.get("X-Request-ID") != request_id:
        raise PublicRuntimeError(f"backend request-id correlation failed: {backend_status}, {backend_headers}")
    evidence["backendReady"] = backend_ready
    evidence["backendRequestId"] = backend_headers.get("X-Request-ID")

    ai_status, ai_headers, ai_ready = _request_with_headers("GET", ai_url() + "/health/ready", request_id)
    if ai_status != 200 or ai_headers.get("X-Request-ID") != request_id:
        raise PublicRuntimeError(f"AI request-id correlation failed: {ai_status}, {ai_headers}")
    evidence["aiReady"] = ai_ready
    evidence["aiRequestId"] = ai_headers.get("X-Request-ID")

    admin_token = _admin_token()
    summary = assert_litemall_ok(request_json("GET", backend_url() + "/admin/ai/dashboard/summary", None, _admin_headers(admin_token)), "dashboard summary")
    evidence["dashboardSummary"] = summary

    backend_metrics = request_json("GET", backend_url() + "/public/runtime/metrics")
    ai_metrics = request_json("GET", ai_url() + "/metrics")
    required_backend_keys = ["httpRequestTotal", "httpDurationMsTotal", "aiAnalysisTotal", "aiAnalysisFailureTotal"]
    runtime_metrics = backend_metrics.get("runtimeMetrics") or {}
    missing = [key for key in required_backend_keys if key not in runtime_metrics]
    if missing:
        raise PublicRuntimeError(f"backend metrics missing keys: {missing}")
    if "http_request_total" not in (ai_metrics.get("metrics") or {}):
        raise PublicRuntimeError(f"AI metrics missing http_request_total: {ai_metrics}")
    evidence["backendMetrics"] = backend_metrics
    evidence["aiMetrics"] = ai_metrics

    write_evidence("observability-smoke-summary.json", evidence)
    print("PUBLIC_OBSERVABILITY_PASS")


if __name__ == "__main__":
    main_guard(main)
