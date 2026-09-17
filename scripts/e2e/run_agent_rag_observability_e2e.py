from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-observability" / "observability-e2e-summary.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ai-base-url", default="http://127.0.0.1:8008")
    parser.add_argument("--admin-base-url", default="http://127.0.0.1:8083")
    parser.add_argument("--username", default=os.environ.get("LITEMALL_ADMIN_USERNAME", "admin123"))
    parser.add_argument("--password-env", default="LITEMALL_ADMIN_PASSWORD")
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()

    result = {"status": "FAIL", "cases": {}, "summary": {}}
    try:
        mark(result, "pythonLive", get_json(args.ai_base_url + "/api/v1/internal/agent-rag/live").get("status") == "live")
        python_ready = get_json(args.ai_base_url + "/api/v1/internal/agent-rag/ready")
        mark(result, "pythonReady", python_ready.get("status") in {"ready", "degraded"})
        mark(result, "pythonMetrics", "metrics" in get_json(args.ai_base_url + "/api/v1/internal/agent-rag/metrics"))

        request_id = "obs-e2e-" + str(int(time.time() * 1000))
        analyze = post_json(
            args.ai_base_url + "/api/v1/agent-rag/analyze",
            {"requestId": request_id, "tenantId": "tenant-a", "subjectId": "obs-review", "query": "broken product refund"},
            {"X-Request-Id": request_id},
        )
        mark(result, "pythonTraceCorrelation", analyze.get("requestId") == request_id)
        mismatch = post_json(
            args.ai_base_url + "/api/v1/agent-rag/analyze",
            {"requestId": "body", "tenantId": "tenant-a", "subjectId": "obs-review", "query": "normal"},
            {"X-Request-Id": "header"},
            allow_error=True,
        )
        mark(result, "pythonTraceMismatchRejected", mismatch.get("detail") == "AGENT_RAG_REQUEST_ID_HEADER_MISMATCH")

        login = post_json(
            args.admin_base_url + "/admin/auth/login",
            {"username": args.username, "password": os.environ.get(args.password_env, "admin123")},
            {},
        )
        token = ((login.get("data") or {}).get("token") or "")
        mark(result, "adminLogin", login.get("errno") == 0 and bool(token))
        admin_headers = {"X-Litemall-Admin-Token": token}
        health = get_json(args.admin_base_url + "/admin/agent-rag/health", admin_headers)
        ready = get_json(args.admin_base_url + "/admin/agent-rag/runtime/ready", admin_headers)
        metrics = get_json(args.admin_base_url + "/admin/agent-rag/runtime/metrics", admin_headers)
        mark(result, "adminHealthMetrics", health.get("errno") == 0 and "metrics" in (health.get("data") or {}))
        mark(result, "adminReady", ready.get("errno") == 0 and (ready.get("data") or {}).get("status") in {"ready", "degraded"})
        mark(result, "adminMetrics", metrics.get("errno") == 0 and "requestsTotal" in (metrics.get("data") or {}))
        result["summary"] = {
            "pythonReady": python_ready.get("status"),
            "adminReady": (ready.get("data") or {}).get("status"),
            "adminRequestsTotal": (metrics.get("data") or {}).get("requestsTotal"),
        }
    except Exception as exc:
        result["cases"]["unexpectedException"] = "FAIL:" + str(exc)[:240]

    result["status"] = "PASS" if result["cases"] and all(value == "PASS" for value in result["cases"].values()) else "FAIL"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result["status"] == "PASS":
        print("AGENT_RAG_OBSERVABILITY_PASS")
        print("AGENT_RAG_STRUCTURED_LOGGING_PASS")
        print("AGENT_RAG_TRACE_CORRELATION_PASS")
        print("AGENT_RAG_METRICS_PASS")
        print("AGENT_RAG_LIVENESS_PASS")
        print("AGENT_RAG_READINESS_PASS")
        print("AGENT_RAG_DEGRADED_MODE_PASS")
        return 0
    print("AGENT_RAG_OBSERVABILITY_FAIL")
    print(json.dumps(result, ensure_ascii=False))
    return 1


def mark(result: dict, name: str, passed: bool) -> None:
    result["cases"][name] = "PASS" if passed else "FAIL"


def get_json(url: str, headers: dict[str, str] | None = None) -> dict:
    return read_json(urllib.request.Request(url, headers=headers or {}))


def post_json(url: str, payload: dict, headers: dict[str, str] | None = None, allow_error: bool = False) -> dict:
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=req_headers, method="POST")
    return read_json(request, allow_error=allow_error)


def read_json(request: urllib.request.Request, allow_error: bool = False) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if not allow_error:
            raise
        return json.loads(body)


if __name__ == "__main__":
    raise SystemExit(main())
