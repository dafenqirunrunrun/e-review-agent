"""Lossless schema migration for persisted review governance snapshots.

This command deliberately does not call the AI service. It only makes legacy
snapshots renderable under the current governance contract.
"""

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

from app.contracts.governance_history import (  # noqa: E402
    CURRENT_GOVERNANCE_SCHEMA_VERSION,
    GOVERNANCE_SCHEMA_V1,
    HUMAN_RESOLVED_STATUSES,
    migrate_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Lossless, idempotent migration for historical review governance snapshots.")
    parser.add_argument("--snapshot-json", default="", help="Optional exported rows or controlled test fixture JSON.")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--task-id", type=int, default=None)
    parser.add_argument("--review-id", default="")
    parser.add_argument("--from-version", default=GOVERNANCE_SCHEMA_V1)
    parser.add_argument("--to-version", default=CURRENT_GOVERNANCE_SCHEMA_VERSION)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true", help="Persist snapshots with an optimistic concurrency guard.")
    args = parser.parse_args()
    if args.to_version != CURRENT_GOVERNANCE_SCHEMA_VERSION:
        raise SystemExit("Only the current target version is supported: " + CURRENT_GOVERNANCE_SCHEMA_VERSION)

    rows = _load_rows(args.snapshot_json, args.limit, args.task_id, args.review_id)
    report = _report(rows, args)
    if args.apply:
        report["dryRun"] = False
        report["apply"] = _apply(report["items"])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _report(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schemaVersion": "review-governance-history-migration-v2", "dryRun": True,
        "fromVersion": args.from_version, "toVersion": args.to_version, "total": len(rows),
        "alreadyCurrent": 0, "migratable": 0, "unknown": 0, "conflict": 0,
        "humanResolved": 0, "failed": 0, "riskTypeChanged": 0,
        "evidenceStatusChanged": 0, "decisionChanged": 0, "items": [],
    }
    for index, row in enumerate(rows, start=1):
        try:
            item = _inspect(row, index)
            report["items"].append(item)
            report[_bucket_key(item["outcome"])] += 1
            report["humanResolved"] += int(item["humanResolved"])
            report["riskTypeChanged"] += int(item["diff"]["riskTypes"]["changed"])
            report["evidenceStatusChanged"] += int(item["diff"]["evidenceStatus"]["changed"])
            report["decisionChanged"] += int(item["diff"]["decision"]["changed"])
        except Exception as exc:
            report["failed"] += 1
            report["items"].append({"row": index, "outcome": "failed", "error": str(exc)[:160]})
    return report


def _inspect(row: dict[str, Any], index: int) -> dict[str, Any]:
    trace_text = str(row.get("workflowTraceJson") or "")
    snapshot = _extract_snapshot(trace_text)
    status = str(row.get("status") or "").lower()
    migration = migrate_snapshot(snapshot, review_text=str(row.get("reviewText") or ""), task_status=status)
    before, after = snapshot or {}, migration.snapshot
    return {
        "row": index, "analysisId": row.get("analysisId"), "reviewId": row.get("reviewId"),
        "riskTaskId": row.get("riskTaskId"), "taskStatus": status or None,
        "humanResolved": status in HUMAN_RESOLVED_STATUSES, "outcome": migration.outcome,
        "unknownRiskTypes": migration.unknown_risk_types, "requiresReevaluation": migration.requires_reevaluation,
        "changes": migration.changes,
        "diff": {
            "riskTypes": _diff(before.get("riskTypes"), after.get("riskTypes")),
            "evidenceStatus": _diff(before.get("evidenceStatus"), after.get("evidenceStatus")),
            "decision": _diff(_decision(before), _decision(after)),
        },
        "hasSnapshot": snapshot is not None, "originalSnapshot": before,
        "migratedSnapshot": after, "originalTrace": trace_text,
    }


def _bucket_key(outcome: str) -> str:
    return {"already_current": "alreadyCurrent", "migrated": "migratable", "unknown": "unknown", "requires_reevaluation": "conflict"}.get(outcome, "unknown")


def _diff(old: Any, new: Any) -> dict[str, Any]:
    return {"from": old, "to": new, "changed": old != new}


def _decision(snapshot: dict[str, Any]) -> Any:
    decision = snapshot.get("decision") if isinstance(snapshot, dict) else None
    return decision.get("code") if isinstance(decision, dict) else None


def _extract_snapshot(trace_text: str) -> dict[str, Any] | None:
    if not trace_text:
        return None
    try:
        trace = json.loads(trace_text)
    except json.JSONDecodeError:
        return None
    if isinstance(trace, dict):
        return trace.get("reviewGovernance") if isinstance(trace.get("reviewGovernance"), dict) else trace
    if not isinstance(trace, list):
        return None
    for step in trace:
        if isinstance(step, dict) and step.get("node") == "review_governance_snapshot" and isinstance(step.get("output"), dict):
            return step["output"]
    return None


def _replace_snapshot(trace_text: str, migrated: dict[str, Any]) -> str:
    trace = json.loads(trace_text)
    if isinstance(trace, list):
        for step in trace:
            if isinstance(step, dict) and step.get("node") == "review_governance_snapshot":
                step["output"] = migrated
                return json.dumps(trace, ensure_ascii=False, separators=(",", ":"))
    if isinstance(trace, dict) and isinstance(trace.get("reviewGovernance"), dict):
        trace["reviewGovernance"] = migrated
        return json.dumps(trace, ensure_ascii=False, separators=(",", ":"))
    raise ValueError("no governance snapshot in workflow trace")


def _load_rows(path: str, limit: int, task_id: int | None, review_id: str) -> list[dict[str, Any]]:
    if path:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        rows = data if isinstance(data, list) else data.get("rows", [])
        return _filter_rows([item for item in rows if isinstance(item, dict)], limit, task_id, review_id)
    return _load_db_rows(limit, task_id, review_id)


def _filter_rows(rows: list[dict[str, Any]], limit: int, task_id: int | None, review_id: str) -> list[dict[str, Any]]:
    filtered = [row for row in rows if task_id is None or row.get("riskTaskId") == task_id]
    if review_id:
        filtered = [row for row in filtered if str(row.get("reviewId")) == review_id]
    return filtered[:max(1, min(limit, 1000))]


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
            cursor.execute("select a.id analysisId, a.review_id reviewId, a.review_text reviewText, a.workflow_trace_json workflowTraceJson, t.id riskTaskId, t.status status, t.handler handler, t.handle_note handleNote from litemall_review_ai_analysis a left join litemall_ai_review_risk_task t on t.analysis_id=a.id and t.deleted=0 where " + " and ".join(where) + " order by a.id desc limit %s", params)
            return list(cursor.fetchall())
    finally:
        connection.close()


def _apply(items: list[dict[str, Any]]) -> dict[str, int]:
    try:
        import pymysql
    except Exception as exc:
        raise SystemExit("pymysql is required for --apply: " + str(exc))
    connection = pymysql.connect(host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_PORT", "3306")), user=os.getenv("MYSQL_USERNAME", "root"), password=os.getenv("MYSQL_PASSWORD", ""), database=os.getenv("MYSQL_DATABASE", "litemall"), charset="utf8mb4")
    result = {"analysisRows": 0, "alreadyCurrent": 0, "conflict": 0, "skipped": 0}
    try:
        with connection.cursor() as cursor:
            for item in items:
                if item.get("outcome") == "already_current":
                    result["alreadyCurrent"] += 1
                    continue
                if item.get("outcome") == "failed" or not item.get("analysisId") or not item.get("hasSnapshot"):
                    result["skipped"] += 1
                    continue
                new_trace = _replace_snapshot(item["originalTrace"], item["migratedSnapshot"])
                cursor.execute("update litemall_review_ai_analysis set workflow_trace_json=%s where id=%s and workflow_trace_json=%s", (new_trace, item["analysisId"], item["originalTrace"]))
                if cursor.rowcount:
                    result["analysisRows"] += 1
                else:
                    result["conflict"] += 1
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
