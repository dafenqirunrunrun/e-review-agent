from __future__ import annotations

import os

from public_runtime_common import (
    PublicRuntimeError,
    admin_url,
    ai_url,
    backend_url,
    customer_url,
    main_guard,
    request_json,
    request_text,
    run_command,
    wait_until,
    write_evidence,
)


def check_mysql() -> str:
    project = os.getenv("PUBLIC_COMPOSE_PROJECT", "")
    if not project:
        return "not_checked_no_compose_project"
    run_command(["docker", "compose", "-p", project, "-f", "compose.public.yml", "exec", "-T", "mysql", "mysqladmin", "ping", "-h", "127.0.0.1", "-ulitemall", "-pchange_me_for_local_only", "--silent"])
    return "healthy"


def main() -> None:
    results = {}
    results["mysql"] = wait_until("MySQL", check_mysql, timeout_seconds=180)
    results["aiLive"] = wait_until("AI liveness", lambda: request_json("GET", ai_url() + "/health/live"), timeout_seconds=120)
    ai_ready = wait_until("AI readiness", lambda: request_json("GET", ai_url() + "/health/ready"), timeout_seconds=120)
    if ai_ready.get("runtimeMode") != "public-rule" or ai_ready.get("engineType") != "rule" or ai_ready.get("modelLoaded") is not False:
        raise PublicRuntimeError(f"AI public runtime boundary failed: {ai_ready}")
    results["aiReady"] = ai_ready
    backend_ready = wait_until("backend readiness", lambda: request_json("GET", backend_url() + "/public/runtime/ready"), timeout_seconds=240)
    if backend_ready.get("status") != "ready":
        raise PublicRuntimeError(f"Backend not ready: {backend_ready}")
    results["backendReady"] = backend_ready
    results["adminPage"] = wait_until("admin page", lambda: "html" if request_text(admin_url() + "/") else "empty", timeout_seconds=120)
    results["customerPage"] = wait_until("customer page", lambda: "html" if request_text(customer_url() + "/") else "empty", timeout_seconds=120)
    write_evidence("health-summary.json", results)
    print("PUBLIC_SERVICE_HEALTH_PASS")


if __name__ == "__main__":
    main_guard(main)
