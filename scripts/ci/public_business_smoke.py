from __future__ import annotations

import os
import time

from public_runtime_common import (
    PublicRuntimeError,
    ai_url,
    backend_url,
    main_guard,
    request_json,
    assert_litemall_ok,
    write_evidence,
)


def _admin_token() -> str:
    username = os.getenv("PUBLIC_CI_ADMIN_USERNAME", "ci_public_admin")
    password = os.getenv("PUBLIC_CI_ADMIN_PASSWORD", "public_ci_admin_123")
    data = assert_litemall_ok(request_json("POST", backend_url() + "/admin/auth/login", {"username": username, "password": password}), "admin login")
    token = data.get("token")
    if not token:
        raise PublicRuntimeError("admin login did not return token")
    return str(token)


def _user_token() -> str:
    username = os.getenv("PUBLIC_CI_USER_USERNAME", "ci_public_user")
    password = os.getenv("PUBLIC_CI_USER_PASSWORD", "public_ci_user_123")
    data = assert_litemall_ok(request_json("POST", backend_url() + "/wx/auth/login", {"username": username, "password": password}), "user login")
    token = data.get("token")
    if not token:
        raise PublicRuntimeError("user login did not return token")
    return str(token)


def _admin_headers(token: str) -> dict[str, str]:
    return {"X-Litemall-Admin-Token": token}


def _user_headers(token: str) -> dict[str, str]:
    return {"X-Litemall-Token": token}


def _submit_comment(user_token: str, order_goods_id: int, text: str, star: int) -> None:
    payload = {
        "orderGoodsId": order_goods_id,
        "content": text,
        "star": star,
        "hasPicture": True,
        "picUrls": ["https://example.com/public-ci-review.jpg"],
    }
    assert_litemall_ok(request_json("POST", backend_url() + "/wx/order/comment", payload, _user_headers(user_token)), f"submit comment {order_goods_id}")


def _list_comments(admin_token: str) -> list[dict]:
    data = assert_litemall_ok(request_json("GET", backend_url() + "/admin/comment/list?userId=1&valueId=1181000&page=1&limit=100", None, _admin_headers(admin_token)), "comment list")
    return data.get("list") or []


def _find_comment_id(admin_token: str, marker: str) -> int:
    for row in _list_comments(admin_token):
        if marker in str(row.get("content") or ""):
            comment_id = row.get("id")
            if comment_id is not None:
                return int(comment_id)
    raise PublicRuntimeError(f"submitted comment marker was not visible in admin comment list: {marker}")


def _run_patrol(admin_token: str) -> dict:
    data = assert_litemall_ok(request_json("POST", backend_url() + "/admin/ai/patrol/run-once", {}, _admin_headers(admin_token), timeout=90), "patrol run-once")
    if data.get("status") != "success":
        raise PublicRuntimeError(f"patrol did not finish successfully: {data}")
    return data


def _list_analyses(admin_token: str) -> list[dict]:
    data = assert_litemall_ok(request_json("GET", backend_url() + "/admin/ai/review/list?productId=1181000&page=1&limit=50", None, _admin_headers(admin_token)), "analysis list")
    return data.get("list") or []


def _list_risks(admin_token: str, status: str | None = None) -> list[dict]:
    suffix = "&status=" + status if status else ""
    data = assert_litemall_ok(request_json("GET", backend_url() + "/admin/ai/risk/list?page=1&limit=50" + suffix, None, _admin_headers(admin_token)), "risk list")
    return data.get("list") or []


def _source_id(row: dict) -> int | None:
    return row.get("sourceId") or row.get("source_id")


def _source_type(row: dict) -> str | None:
    return row.get("sourceType") or row.get("source_type")


def main() -> None:
    evidence: dict = {}
    ai_ready = request_json("GET", ai_url() + "/health/ready")
    if ai_ready.get("runtimeMode") != "public-rule" or ai_ready.get("engineType") != "rule" or ai_ready.get("modelLoaded") is not False:
        raise PublicRuntimeError(f"public AI mode check failed: {ai_ready}")
    evidence["publicAiMode"] = ai_ready

    admin_token = _admin_token()
    user_token = _user_token()
    before_summary = assert_litemall_ok(request_json("GET", backend_url() + "/admin/ai/dashboard/summary", None, _admin_headers(admin_token)), "dashboard before")
    evidence["dashboardBefore"] = before_summary

    marker = f"ci_public_{os.getenv('GITHUB_RUN_ID', str(int(time.time())))}"
    normal_marker = marker + "_normal"
    risk_marker = marker + "_risk"
    _submit_comment(user_token, 190001, f"{normal_marker} normal review: good quality and comfortable product.", 5)
    _submit_comment(user_token, 190002, f"{risk_marker} high risk review: bad product, refund requested, safety concern after-sales follow up needed.", 1)
    submitted_comment_ids = [_find_comment_id(admin_token, normal_marker), _find_comment_id(admin_token, risk_marker)]
    evidence["commentsSubmitted"] = [
        {"orderGoodsId": 190001, "commentId": submitted_comment_ids[0]},
        {"orderGoodsId": 190002, "commentId": submitted_comment_ids[1]},
    ]

    first_patrol = _run_patrol(admin_token)
    evidence["firstPatrol"] = first_patrol
    analyses = _list_analyses(admin_token)
    source_ids = {_source_id(row) for row in analyses if _source_type(row) == "litemall_comment"}
    missing_source_ids = [comment_id for comment_id in submitted_comment_ids if comment_id not in source_ids]
    if missing_source_ids:
        raise PublicRuntimeError(f"submitted litemall_comment analyses missing for source ids: {missing_source_ids}; got {source_ids}")
    evidence["analysisSourceIds"] = sorted([sid for sid in source_ids if sid is not None])

    risks = _list_risks(admin_token, "pending")
    litemall_risks = [row for row in risks if _source_type(row) == "litemall_comment"]
    if not litemall_risks:
        raise PublicRuntimeError("expected pending litemall_comment risk task")
    risk_task = litemall_risks[0]
    evidence["riskTaskBeforeHandle"] = risk_task

    count_before = len(_list_analyses(admin_token))
    risk_count_before = len(_list_risks(admin_token))
    second_patrol = _run_patrol(admin_token)
    count_after = len(_list_analyses(admin_token))
    risk_count_after = len(_list_risks(admin_token))
    if count_before != count_after or risk_count_before != risk_count_after:
        raise PublicRuntimeError(f"idempotency failed: analysis {count_before}->{count_after}, risk {risk_count_before}->{risk_count_after}, patrol={second_patrol}")
    evidence["idempotency"] = {"analysisCount": count_after, "riskCount": risk_count_after, "secondPatrol": second_patrol}

    risk_id = risk_task.get("id")
    assert_litemall_ok(request_json("POST", backend_url() + "/admin/ai/operation/handle", {
        "riskTaskId": risk_id,
        "actionType": "accept_suggestion",
        "newStatus": "handled",
        "operator": "public-ci",
        "note": "Handled by public runtime smoke E2E.",
        "feedbackType": "accept",
        "feedbackNote": "Public smoke accepted the generated operation suggestion.",
    }, _admin_headers(admin_token)), "operation handle")
    after_summary = assert_litemall_ok(request_json("GET", backend_url() + "/admin/ai/dashboard/summary", None, _admin_headers(admin_token)), "dashboard after")
    evidence["dashboardAfter"] = after_summary
    evidence["handledRiskTaskId"] = risk_id
    write_evidence("business-smoke-summary.json", evidence)
    print("PUBLIC_BUSINESS_E2E_PASS")
    print("PUBLIC_IDEMPOTENCY_PASS")


if __name__ == "__main__":
    main_guard(main)
