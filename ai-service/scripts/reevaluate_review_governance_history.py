"""Explicitly re-evaluate only historical snapshots marked requiresReevaluation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.governance_reevaluation import DEFAULT_REASON_CODE, GovernanceReevaluationService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Explicit, append-only historical governance re-evaluation.")
    parser.add_argument("--fixture", default="", help="Controlled exported rows; uses the same core service as database mode.")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--task-id", type=int, default=None)
    parser.add_argument("--review-id", default="")
    parser.add_argument("--reason", default=DEFAULT_REASON_CODE)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true", help="Append an evaluation revision to matching analysis snapshots.")
    args = parser.parse_args()
    rows = _load_rows(args.fixture, args.limit, args.task_id, args.review_id)
    report = _report(rows, args, GovernanceReevaluationService())
    if args.apply:
        report["dryRun"] = False
        report["apply"] = _apply(report["items"])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _report(rows: list[dict[str, Any]], args: argparse.Namespace, service: GovernanceReevaluationService) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schemaVersion": "review-governance-reevaluation-v1", "dryRun": True,
        "reasonCode": str(args.reason).upper(), "totalCandidates": 0, "evaluated": 0,
        "unchanged": 0, "minorChanged": 0, "materialChanged": 0,
        "humanResolvedProtected": 0, "needsHumanAttention": 0,
        "alreadyReevaluated": 0, "failed": 0, "riskTypeDriftCount": 0,
        "evidenceStatusDriftCount": 0, "decisionDriftCount": 0, "items": [],
    }
    for row in rows:
        snapshot = _extract_snapshot(str(row.get("workflowTraceJson") or ""))
        if not isinstance(snapshot, dict) or snapshot.get("requiresReevaluation") is not True:
            continue
        report["totalCandidates"] += 1
        result = service.reevaluate(snapshot, row, reason_code=args.reason)
        item = {"analysisId": row.get("analysisId"), "reviewId": row.get("reviewId"), "riskTaskId": row.get("riskTaskId"), "taskStatus": row.get("status"), "outcome": result.outcome, "error": result.error, "originalTrace": row.get("workflowTraceJson"), "updatedSnapshot": result.snapshot}
        if result.diff:
            item["diff"] = result.diff
            severity = result.diff["changeSeverity"]
            report[{"NONE": "unchanged", "MINOR": "minorChanged", "MATERIAL": "materialChanged"}[severity]] += 1
            report["riskTypeDriftCount"] += int(result.diff["riskTypesChanged"])
            report["evidenceStatusDriftCount"] += int(result.diff["evidenceStatusChanged"])
            report["decisionDriftCount"] += int(result.diff["decisionChanged"])
        if result.outcome == "evaluated":
            report["evaluated"] += 1
        elif result.outcome == "already_reevaluated":
            report["alreadyReevaluated"] += 1
        elif result.outcome == "failed":
            report["failed"] += 1
        if result.snapshot.get("historicalDecisionDrift"):
            report["humanResolvedProtected"] += 1
        if result.snapshot.get("needsHumanAttention"):
            report["needsHumanAttention"] += 1
        report["items"].append(item)
    return report


def _extract_snapshot(trace_text: str) -> dict[str, Any] | None:
    try:
        trace = json.loads(trace_text)
    except (TypeError, json.JSONDecodeError):
        return None
    if isinstance(trace, dict):
        return trace.get("reviewGovernance") if isinstance(trace.get("reviewGovernance"), dict) else trace
    for step in trace if isinstance(trace, list) else []:
        if isinstance(step, dict) and step.get("node") == "review_governance_snapshot" and isinstance(step.get("output"), dict):
            return step["output"]
    return None


def _replace_snapshot(trace_text: str, updated: dict[str, Any]) -> str:
    trace = json.loads(trace_text)
    if isinstance(trace, list):
        for step in trace:
            if isinstance(step, dict) and step.get("node") == "review_governance_snapshot":
                step["output"] = updated
                return json.dumps(trace, ensure_ascii=False, separators=(",", ":"))
    if isinstance(trace, dict) and isinstance(trace.get("reviewGovernance"), dict):
        trace["reviewGovernance"] = updated
        return json.dumps(trace, ensure_ascii=False, separators=(",", ":"))
    raise ValueError("no governance snapshot in workflow trace")


def _load_rows(fixture: str, limit: int, task_id: int | None, review_id: str) -> list[dict[str, Any]]:
    if fixture:
        data = json.loads(Path(fixture).read_text(encoding="utf-8-sig"))
        rows = data if isinstance(data, list) else data.get("rows", [])
        return _filter(rows, limit, task_id, review_id)
    return _load_db_rows(limit, task_id, review_id)


def _filter(rows: Any, limit: int, task_id: int | None, review_id: str) -> list[dict[str, Any]]:
    values = [row for row in rows if isinstance(row, dict)]
    if task_id is not None:
        values = [row for row in values if row.get("riskTaskId") == task_id]
    if review_id:
        values = [row for row in values if str(row.get("reviewId")) == review_id]
    return values[:max(1, min(limit, 1000))]


def _load_db_rows(limit: int, task_id: int | None, review_id: str) -> list[dict[str, Any]]:
    try:
        import pymysql
    except Exception:
        return []
    connection = pymysql.connect(host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_PORT", "3306")), user=os.getenv("MYSQL_USERNAME", "root"), password=os.getenv("MYSQL_PASSWORD", ""), database=os.getenv("MYSQL_DATABASE", "litemall"), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    try:
        where, params = ["a.deleted=0"], []
        if task_id is not None:
            where.append("t.id=%s")
            params.append(task_id)
        if review_id:
            where.append("a.review_id=%s")
            params.append(review_id)
        params.append(max(1, min(limit, 1000)))
        with connection.cursor() as cursor:
            cursor.execute("select a.id analysisId, a.review_id reviewId, a.product_id productId, a.product_name productName, a.review_text reviewText, a.rating rating, a.image_urls imageUrls, a.workflow_trace_json workflowTraceJson, t.id riskTaskId, t.status status, t.handler handler, t.handle_note handleNote from litemall_review_ai_analysis a left join litemall_ai_review_risk_task t on t.analysis_id=a.id and t.deleted=0 where " + " and ".join(where) + " order by a.id desc limit %s", params)
            return list(cursor.fetchall())
    finally:
        connection.close()


def _apply(items: list[dict[str, Any]]) -> dict[str, int]:
    try:
        import pymysql
    except Exception as exc:
        raise SystemExit("pymysql is required for --apply: " + str(exc))
    connection = pymysql.connect(host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_PORT", "3306")), user=os.getenv("MYSQL_USERNAME", "root"), password=os.getenv("MYSQL_PASSWORD", ""), database=os.getenv("MYSQL_DATABASE", "litemall"), charset="utf8mb4")
    report = {"analysisRows": 0, "alreadyReevaluated": 0, "conflict": 0, "skipped": 0}
    try:
        with connection.cursor() as cursor:
            for item in items:
                if item["outcome"] == "already_reevaluated":
                    report["alreadyReevaluated"] += 1
                    continue
                if item["outcome"] != "evaluated" or not item.get("analysisId"):
                    report["skipped"] += 1
                    continue
                trace = _replace_snapshot(str(item["originalTrace"]), item["updatedSnapshot"])
                cursor.execute("update litemall_review_ai_analysis set workflow_trace_json=%s where id=%s and workflow_trace_json=%s", (trace, item["analysisId"], item["originalTrace"]))
                if cursor.rowcount:
                    report["analysisRows"] += 1
                else:
                    report["conflict"] += 1
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return report


if __name__ == "__main__":
    raise SystemExit(main())
