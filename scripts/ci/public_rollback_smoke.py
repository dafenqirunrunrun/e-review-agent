from __future__ import annotations

import os
import subprocess
from datetime import datetime

from public_runtime_common import PublicRuntimeError, backend_url, main_guard, request_json, run_command, wait_until, write_evidence


def _source_commit() -> str:
    return os.getenv("GITHUB_SHA") or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


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
    write_evidence("rollback-smoke-summary.json", {
        "schemaVersion": "public-backend-restart-recovery-v2",
        "sourceCommit": _source_commit(),
        "workflowRunId": os.getenv("GITHUB_RUN_ID", "local"),
        "generatedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "status": "PASS",
        "mode": "compose-service-restart",
        "applicationVersionRollback": False,
        "databaseRollback": False,
        "blueGreenRollback": False,
        "before": before,
        "after": after,
        "checks": {
            "restartRecovered": True,
            "applicationVersionRollback": False,
        },
        "boundaries": [
            "APPLICATION_VERSION_ROLLBACK_NOT_VERIFIED",
            "DATABASE_ROLLBACK_NOT_VERIFIED",
            "BLUE_GREEN_ROLLBACK_NOT_VERIFIED",
            "PRODUCTION_READY_NOT_CLAIMED",
        ],
    })
    print("PUBLIC_BACKEND_RESTART_RECOVERY_PASS")


if __name__ == "__main__":
    main_guard(main)
