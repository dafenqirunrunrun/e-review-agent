from __future__ import annotations

import os

from public_runtime_common import (
    PublicRuntimeError,
    ai_url,
    backend_url,
    main_guard,
    request_json,
    assert_litemall_ok,
    run_command,
    wait_until,
    write_evidence,
)
from public_business_smoke import _admin_headers, _admin_token, _find_comment_id, _run_patrol, _source_id, _source_type, _submit_comment, _user_token


def _list_analyses(admin_token: str) -> list[dict]:
    data = assert_litemall_ok(request_json("GET", backend_url() + "/admin/ai/review/list?productId=1181000&page=1&limit=50", None, _admin_headers(admin_token)), "analysis list")
    return data.get("list") or []


def _has_source(admin_token: str, source_id: int) -> bool:
    return any(_source_type(row) == "litemall_comment" and _source_id(row) == source_id for row in _list_analyses(admin_token))


def main() -> None:
    project = os.getenv("PUBLIC_COMPOSE_PROJECT")
    if not project:
        raise PublicRuntimeError("PUBLIC_COMPOSE_PROJECT is required for AI unavailable smoke")
    admin_token = _admin_token()
    user_token = _user_token()
    evidence = {}
    run_command(["docker", "compose", "-p", project, "-f", "compose.public.yml", "stop", "ai-service"])
    try:
        marker = "ci_public_unavailable_review"
        _submit_comment(user_token, 190003, f"{marker}: bad product and refund requested during AI outage.", 1)
        comment_id = _find_comment_id(admin_token, marker)
        evidence["submittedCommentId"] = comment_id
        failed_patrol = _run_patrol(admin_token)
        evidence["patrolWhileAiStopped"] = failed_patrol
        if failed_patrol.get("failedCount", 0) < 1:
            raise PublicRuntimeError(f"expected at least one failed analysis while AI stopped: {failed_patrol}")
        if _has_source(admin_token, comment_id):
            raise PublicRuntimeError("analysis was incorrectly marked successful while AI service was stopped")
    finally:
        run_command(["docker", "compose", "-p", project, "-f", "compose.public.yml", "start", "ai-service"])
    wait_until("AI readiness after restart", lambda: request_json("GET", ai_url() + "/health/ready"), timeout_seconds=120)
    recovered_patrol = _run_patrol(admin_token)
    evidence["patrolAfterAiRestart"] = recovered_patrol
    if not _has_source(admin_token, comment_id):
        raise PublicRuntimeError("analysis did not recover after AI service restart")
    write_evidence("failure-smoke-summary.json", evidence)
    print("PUBLIC_AI_UNAVAILABLE_BEHAVIOR_PASS")


if __name__ == "__main__":
    main_guard(main)
