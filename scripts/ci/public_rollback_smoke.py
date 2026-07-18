from __future__ import annotations

import os

from public_runtime_common import PublicRuntimeError, backend_url, main_guard, request_json, run_command, wait_until, write_evidence


def main() -> None:
    project = os.getenv("PUBLIC_COMPOSE_PROJECT")
    if not project:
        raise PublicRuntimeError("PUBLIC_COMPOSE_PROJECT is required for rollback smoke")
    before = request_json("GET", backend_url() + "/public/runtime/ready")
    if before.get("status") != "ready":
        raise PublicRuntimeError(f"backend was not ready before rollback smoke: {before}")
    run_command(["docker", "compose", "-p", project, "-f", "compose.public.yml", "restart", "backend"])
    after = wait_until("backend readiness after rollback restart", lambda: request_json("GET", backend_url() + "/public/runtime/ready"), timeout_seconds=180)
    if after.get("status") != "ready":
        raise PublicRuntimeError(f"backend was not ready after restart: {after}")
    write_evidence("rollback-smoke-summary.json", {"before": before, "after": after, "rollbackMode": "compose-service-restart"})
    print("PUBLIC_ROLLBACK_PASS")


if __name__ == "__main__":
    main_guard(main)
