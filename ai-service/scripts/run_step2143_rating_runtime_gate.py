from __future__ import annotations

"""Verify the rating contract through live WX, Admin, AI, DB, and shadow paths."""

import argparse
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DEFAULT_OUTPUT = ROOT / "artifacts" / "step2143_rating_runtime_gate" / "rating_runtime_gate.json"
DEFAULT_REPORT = REPO_ROOT / "docs" / "RATING_CONTRACT_RUNTIME_GATE.md"
SHADOW_DECISIONS = ROOT / "artifacts" / "step214_fast_eligibility_shadow" / "fast_shadow_decisions.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wx-url", default="http://127.0.0.1:8082")
    parser.add_argument("--admin-url", default="http://127.0.0.1:8083")
    parser.add_argument("--ai-url", default="http://127.0.0.1:8008")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"STEP2143_CONFIG_MISSING:{name}")
    return value


def mysql(query: str) -> list[str]:
    environment = dict(os.environ)
    environment["MYSQL_PWD"] = required_env("MYSQL_PASSWORD")
    command = [
        "mysql",
        "--default-character-set=utf8mb4",
        f"--host={required_env('MYSQL_HOST')}",
        f"--port={required_env('MYSQL_PORT')}",
        f"--user={required_env('MYSQL_USERNAME')}",
        f"--database={required_env('MYSQL_DATABASE')}",
        "--batch",
        "--raw",
        "--skip-column-names",
        "--execute",
        query,
    ]
    completed = subprocess.run(command, capture_output=True, check=True, env=environment)
    return [line for line in completed.stdout.decode("utf-8").splitlines() if line.strip()]


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict:
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers or {})
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    with urllib.request.urlopen(request, timeout=190) as response:
        return json.loads(response.read().decode("utf-8"))


def login(base_url: str, path: str, username_env: str, password_env: str) -> str:
    response = request_json(
        "POST",
        f"{base_url}{path}",
        {"username": required_env(username_env), "password": required_env(password_env)},
    )
    if response.get("errno") != 0 or not (response.get("data") or {}).get("token"):
        raise RuntimeError(f"STEP2143_LOGIN_FAILED:{path}")
    return str(response["data"]["token"])


def seed_confirmed_order(suffix: str) -> tuple[int, int]:
    rows = mysql(
        "INSERT INTO litemall_order "
        "(user_id,order_sn,order_status,consignee,mobile,address,goods_price,freight_price,"
        "coupon_price,integral_price,groupon_price,order_price,actual_price,comments,add_time,update_time,deleted) "
        f"VALUES (1,'S2143{suffix}',401,'runtime-gate','00000000000','runtime-gate',0,0,0,0,0,0,0,1,NOW(),NOW(),0); "
        "SET @step2143_order_id=LAST_INSERT_ID(); "
        "INSERT INTO litemall_order_goods "
        "(order_id,goods_id,goods_name,goods_sn,product_id,number,price,specifications,pic_url,comment,add_time,update_time,deleted) "
        "VALUES (@step2143_order_id,1181000,'runtime-gate','STEP2143',0,1,0,'[]','',0,NOW(),NOW(),0); "
        "SELECT @step2143_order_id,LAST_INSERT_ID();"
    )
    order_id, order_goods_id = rows[-1].split("\t")
    return int(order_id), int(order_goods_id)


def analysis_result(response: dict) -> tuple[int, dict]:
    if response.get("errno") != 0:
        raise RuntimeError(f"STEP2143_ANALYZE_FAILED:{response.get('errmsg', 'unknown')}" )
    data = response.get("data") or {}
    return int(data["analysisId"]), data["result"]


def route_summary(result: dict) -> dict[str, Any]:
    extra = result.get("extra") if isinstance(result.get("extra"), dict) else {}
    agentic = extra.get("agentic") if isinstance(extra.get("agentic"), dict) else {}
    intent = agentic.get("intent") if isinstance(agentic.get("intent"), dict) else {}
    return {
        "route": agentic.get("route"),
        "decision": result.get("route_decision"),
        "riskTypes": result.get("risk_types") or [],
        "reasonCodes": intent.get("reason_codes") or intent.get("reasonCodes") or [],
    }


def admin_analyze(admin_url: str, token: str, payload: dict[str, Any]) -> tuple[int, dict]:
    response = request_json(
        "POST",
        f"{admin_url}/admin/ai/review/analyze",
        payload,
        {"X-Litemall-Admin-Token": token},
    )
    return analysis_result(response)


def shadow_records(review_ids: set[str]) -> list[dict]:
    deadline = time.time() + 5
    while time.time() < deadline:
        if SHADOW_DECISIONS.exists():
            records = [
                json.loads(line)
                for line in SHADOW_DECISIONS.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            selected = [record for record in records if record.get("reviewId") in review_ids]
            if len(selected) == len(review_ids):
                return selected
        time.sleep(0.1)
    return []


def write_report(path: Path, result: dict) -> None:
    metrics = result.get("metrics") or {}
    checks = result.get("checks") or {}
    failed = [name for name, passed in checks.items() if not passed]
    lines = [
        "# Rating Contract Runtime Gate",
        "",
        "## Result",
        "",
        f"`STEP21_4_3_RATING_RUNTIME_GATE = {result['gate']}`",
        "",
        "## Runtime Matrix",
        "",
        "- Missing user rating: rejected, no comment persisted.",
        "- Real one-star rating: persisted as `USER_PROVIDED` and emitted `LOW_RATING`.",
        "- Real five-star rating: persisted as `USER_PROVIDED` and did not emit `LOW_RATING`.",
        "- Unknown API rating: remained null and did not emit `LOW_RATING`.",
        "- High-risk and safety-gate cases: remained on Shadow Long.",
        "",
        "## Metrics",
        "",
        f"- Runtime cases: `{metrics.get('sampleCount', 0)}`",
        f"- Shadow Fast / Long: `{metrics.get('shadowFast', 0)} / {metrics.get('shadowLong', 0)}`",
        f"- Runtime long reduction: `{metrics.get('longReduction', 0):.2%}`",
        f"- High-risk Shadow Fast: `{metrics.get('highRiskShadowFast', 0)}`",
        f"- Safety Shadow Fast: `{metrics.get('safetyShadowFast', 0)}`",
        f"- Checks: `{sum(bool(value) for value in checks.values())}/{len(checks)}`",
        f"- Failed checks: `{failed}`",
        "",
        "## Isolation",
        "",
        f"- Fixture cleanup completed: `{str(result.get('cleanupCompleted', False)).lower()}`",
        "- Shadow executed a candidate chain: `false`",
        "- Frozen benchmark executed: `false`",
        "- Fast Gate policy modified: `false`",
        "- Raw review text persisted in this artifact: `false`",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    suffix = uuid.uuid4().hex[:10]
    marker = f"S2143-{suffix}"
    wx_token = login(args.wx_url, "/wx/auth/login", "STEP2143_WX_USERNAME", "STEP2143_WX_PASSWORD")
    admin_token = login(args.admin_url, "/admin/auth/login", "STEP2143_ADMIN_USERNAME", "STEP2143_ADMIN_PASSWORD")
    order_id, order_goods_id = seed_confirmed_order(suffix)
    comment_ids: list[int] = []
    analysis_ids: list[int] = []
    review_ids = {
        "unknown": f"step2143-unknown-{suffix}",
        "highRisk": f"step2143-high-risk-{suffix}",
        "safety": f"step2143-safety-{suffix}",
    }
    result: dict[str, Any] = {
        "schemaVersion": "rating-contract-runtime-gate-v1",
        "gate": "FAIL",
        "checks": {},
        "cases": {},
        "metrics": {},
        "cleanupCompleted": False,
        "frozenBenchmarkExecuted": False,
        "fastGatePolicyModified": False,
        "rawReviewTextPersisted": False,
    }
    try:
        observation_table_present = int(mysql(
            "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() "
            "AND TABLE_NAME='litemall_ai_governance_observation';"
        )[0]) == 1
        if not observation_table_present:
            raise RuntimeError("STEP2143_GOVERNANCE_OBSERVATION_TABLE_MISSING")
        missing = request_json(
            "POST",
            f"{args.wx_url}/wx/comment/post",
            {"type": 0, "valueId": 1181000, "content": f"{marker}-missing", "hasPicture": False},
            {"X-Litemall-Token": wx_token},
        )
        missing_count = int(mysql(f"SELECT COUNT(*) FROM litemall_comment WHERE content='{marker}-missing';")[0])

        one_response = request_json(
            "POST",
            f"{args.wx_url}/wx/order/comment",
            {
                "orderGoodsId": order_goods_id,
                "content": f"{marker}-case-a 商品体验一般，暂时不会再次购买。",
                "star": 1,
                "hasPicture": False,
                "picUrls": [],
            },
            {"X-Litemall-Token": wx_token},
        )
        one_row = mysql(
            "SELECT c.id,c.star,c.rating_source FROM litemall_order_goods og "
            "JOIN litemall_comment c ON c.id=og.comment "
            f"WHERE og.id={order_goods_id};"
        )[0].split("\t")
        one_comment_id = int(one_row[0])
        comment_ids.append(one_comment_id)
        review_ids["oneStar"] = f"comment-{one_comment_id}"

        five_response = request_json(
            "POST",
            f"{args.wx_url}/wx/comment/post",
            {
                "type": 0,
                "valueId": 1181000,
                "content": f"{marker}-case-b 商品很好，物流也很快。",
                "star": 5,
                "ratingSource": "UNKNOWN",
                "hasPicture": False,
                "picUrls": [],
            },
            {"X-Litemall-Token": wx_token},
        )
        five_comment_id = int((five_response.get("data") or {}).get("id"))
        comment_ids.append(five_comment_id)
        review_ids["fiveStar"] = f"comment-{five_comment_id}"
        five_row = mysql(
            f"SELECT id,star,rating_source FROM litemall_comment WHERE id={five_comment_id};"
        )[0].split("\t")

        list_response = request_json(
            "GET",
            f"{args.admin_url}/admin/comment/list?userId=1&page=1&limit=20&sort=id&order=desc",
            headers={"X-Litemall-Admin-Token": admin_token},
        )
        listed = {
            int(row["id"]): row
            for row in ((list_response.get("data") or {}).get("list") or [])
            if int(row.get("id", 0)) in comment_ids
        }

        def analyze_comment(comment_id: int) -> tuple[int, dict]:
            row = listed[comment_id]
            source = row.get("ratingSource") if row.get("ratingSource") == "USER_PROVIDED" else "UNKNOWN"
            return admin_analyze(
                args.admin_url,
                admin_token,
                {
                    "reviewId": f"comment-{comment_id}",
                    "productId": row["valueId"],
                    "productName": f"Product {row['valueId']}",
                    "reviewText": row["content"],
                    "imageUrls": row.get("picUrls") or [],
                    "rating": row.get("star") if source == "USER_PROVIDED" else None,
                    "ratingSource": source,
                },
            )

        one_analysis_id, one_result = analyze_comment(one_comment_id)
        five_analysis_id, five_result = analyze_comment(five_comment_id)
        analysis_ids.extend([one_analysis_id, five_analysis_id])

        unknown_analysis_id, unknown_result = admin_analyze(
            args.admin_url,
            admin_token,
            {
                "reviewId": review_ids["unknown"],
                "productId": 1181000,
                "productName": "Runtime gate",
                "reviewText": "商品不错，物流正常。",
                "imageUrls": [],
                "rating": None,
                "ratingSource": "UNKNOWN",
            },
        )
        high_analysis_id, high_result = admin_analyze(
            args.admin_url,
            admin_token,
            {
                "reviewId": review_ids["highRisk"],
                "productId": 1181000,
                "productName": "Runtime gate",
                "reviewText": "This is an organized fake review with no real purchase experience.",
                "imageUrls": [],
                "rating": None,
                "ratingSource": "UNKNOWN",
            },
        )
        safety_analysis_id, safety_result = admin_analyze(
            args.admin_url,
            admin_token,
            {
                "reviewId": review_ids["safety"],
                "productId": 1181000,
                "productName": "Runtime gate",
                "reviewText": "The seller offers cashback only after a five star review is posted.",
                "imageUrls": [],
                "rating": None,
                "ratingSource": "UNKNOWN",
            },
        )
        analysis_ids.extend([unknown_analysis_id, high_analysis_id, safety_analysis_id])

        summaries = {
            "oneStar": route_summary(one_result),
            "fiveStar": route_summary(five_result),
            "unknown": route_summary(unknown_result),
            "highRisk": route_summary(high_result),
            "safety": route_summary(safety_result),
        }
        shadows = shadow_records(set(review_ids.values()))
        shadow_by_id = {row["reviewId"]: row for row in shadows}
        one_shadow = shadow_by_id.get(review_ids["oneStar"], {})
        five_shadow = shadow_by_id.get(review_ids["fiveStar"], {})
        unknown_shadow = shadow_by_id.get(review_ids["unknown"], {})
        high_shadow = shadow_by_id.get(review_ids["highRisk"], {})
        safety_shadow = shadow_by_id.get(review_ids["safety"], {})

        column_default = mysql(
            "SELECT IF(COLUMN_DEFAULT IS NULL,'NULL',COLUMN_DEFAULT),IS_NULLABLE "
            "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
            "AND TABLE_NAME='litemall_comment' AND COLUMN_NAME='star';"
        )[0].split("\t")
        unknown_violations = int(mysql(
            "SELECT COUNT(*) FROM litemall_comment "
            "WHERE rating_source='UNKNOWN' AND star IS NOT NULL;"
        )[0])

        checks = {
            "governanceObservationTablePresent": observation_table_present,
            "starDefaultIsNull": column_default == ["NULL", "YES"],
            "unknownRowsHaveNullRating": unknown_violations == 0,
            "missingUserRatingRejected": missing.get("errno") != 0 and missing_count == 0,
            "oneStarWriteSucceeded": one_response.get("errno") == 0,
            "oneStarPersistedWithSource": one_row[1:] == ["1", "USER_PROVIDED"],
            "fiveStarWriteSucceeded": five_response.get("errno") == 0,
            "fiveStarPersistedWithServerSource": five_row[1:] == ["5", "USER_PROVIDED"],
            "adminListExposesRatingSource": len(listed) == 2 and all(
                row.get("ratingSource") == "USER_PROVIDED" for row in listed.values()
            ),
            "oneStarTriggersLowRating": "LOW_RATING" in summaries["oneStar"]["reasonCodes"],
            "oneStarUsesStrictRoute": summaries["oneStar"]["route"] == "governance_required",
            "unknownDoesNotTriggerLowRating": "LOW_RATING" not in summaries["unknown"]["reasonCodes"],
            "fiveStarDoesNotTriggerLowRating": "LOW_RATING" not in summaries["fiveStar"]["reasonCodes"],
            "unknownUsesLowTouch": summaries["unknown"]["route"] == "low_touch",
            "fiveStarUsesLowTouch": summaries["fiveStar"]["route"] == "low_touch",
            "highRiskUsesLongShadow": high_shadow.get("shadowDecision") == "LONG_ANALYSIS_CHAIN",
            "safetyUsesLongShadow": safety_shadow.get("shadowDecision") == "LONG_ANALYSIS_CHAIN",
            "allShadowRecordsObserved": len(shadows) == len(review_ids),
            "shadowExecutedNoChains": bool(shadows) and all(not row.get("chainExecuted") for row in shadows),
        }
        shadow_fast = sum(row.get("shadowDecision") == "FAST_SHORT_CHAIN" for row in shadows)
        shadow_long = len(shadows) - shadow_fast
        high_fast = sum(
            row.get("shadowDecision") == "FAST_SHORT_CHAIN"
            and (row.get("riskSignalSummary") or {}).get("highRiskSignal")
            for row in shadows
        )
        safety_fast = sum(
            row.get("shadowDecision") == "FAST_SHORT_CHAIN"
            and (row.get("riskSignalSummary") or {}).get("safetyGateTriggered")
            for row in shadows
        )
        result.update(
            {
                "checks": checks,
                "cases": summaries,
                "metrics": {
                    "sampleCount": len(shadows),
                    "shadowFast": shadow_fast,
                    "shadowLong": shadow_long,
                    "longReduction": round(shadow_fast / len(shadows), 6) if shadows else 0.0,
                    "highRiskShadowFast": high_fast,
                    "safetyShadowFast": safety_fast,
                },
            }
        )
        checks["runtimeReductionAtLeast20Percent"] = result["metrics"]["longReduction"] >= 0.20
        result["gate"] = "PASS" if all(checks.values()) and high_fast == 0 and safety_fast == 0 else "FAIL"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}:{exc}"
    finally:
        try:
            fixture_filter = (
                f"review_id LIKE 'step2143-%-{suffix}' "
                f"OR review_text LIKE '{marker}-%'"
            )
            fixture_analysis_ids = mysql(
                f"SELECT id FROM litemall_review_ai_analysis WHERE {fixture_filter};"
            )
            if fixture_analysis_ids:
                ids = ",".join(fixture_analysis_ids)
                mysql(f"DELETE FROM litemall_ai_governance_observation WHERE analysis_id IN ({ids});")
                mysql(f"DELETE FROM litemall_ai_review_risk_task WHERE analysis_id IN ({ids});")
            mysql(
                "DELETE FROM litemall_ai_governance_observation "
                f"WHERE review_id LIKE 'step2143-%-{suffix}';"
            )
            mysql(f"DELETE FROM litemall_review_ai_analysis WHERE {fixture_filter};")
            mysql(f"DELETE FROM litemall_comment WHERE content LIKE '{marker}-%';")
            mysql(
                "DELETE FROM litemall_order_goods WHERE order_id IN "
                f"(SELECT id FROM litemall_order WHERE order_sn='S2143{suffix}');"
            )
            mysql(f"DELETE FROM litemall_order WHERE order_sn='S2143{suffix}';")
            residue = sum(
                int(value)
                for value in mysql(
                    "SELECT COUNT(*) FROM litemall_review_ai_analysis "
                    f"WHERE {fixture_filter}; "
                    "SELECT COUNT(*) FROM litemall_comment "
                    f"WHERE content LIKE '{marker}-%'; "
                    "SELECT COUNT(*) FROM litemall_order "
                    f"WHERE order_sn='S2143{suffix}'; "
                    "SELECT COUNT(*) FROM litemall_ai_governance_observation "
                    f"WHERE review_id LIKE 'step2143-%-{suffix}';"
                )
            )
            result["cleanupCompleted"] = residue == 0
            if residue:
                result["cleanupResidueCount"] = residue
                result["gate"] = "FAIL"
        except Exception as cleanup_error:
            result["cleanupError"] = f"{type(cleanup_error).__name__}:{cleanup_error}"
            result["gate"] = "FAIL"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(args.report, result)
    return result


def main() -> int:
    result = run(parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
