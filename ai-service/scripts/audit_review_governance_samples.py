from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Sample recent governance records and check traceability.")
    parser.add_argument("--snapshot-json", default="", help="Optional exported rows for offline verification.")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    rows = _load_rows(args.snapshot_json)
    sample = random.sample(rows, min(max(0, args.limit), len(rows))) if rows else []
    checked = [_check_row(row) for row in sample]
    summary = {
        "schemaVersion": "review-governance-audit-sampling-v1",
        "totalInput": len(rows),
        "sampleSize": len(sample),
        "linked": sum(1 for row in checked if row["linked"]),
        "missingEvidence": sum(1 for row in checked if "missing_evidence" in row["issues"]),
        "missingReflection": sum(1 for row in checked if "missing_reflection" in row["issues"]),
        "missingHumanReview": sum(1 for row in checked if "missing_human_review" in row["issues"]),
        "rows": checked,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all(row["linked"] for row in checked) else 1 if checked else 0


def _load_rows(snapshot_json: str) -> list[dict[str, Any]]:
    if snapshot_json:
        data = json.loads(Path(snapshot_json).read_text(encoding="utf-8-sig"))
        return data if isinstance(data, list) else data.get("rows", [])
    try:
        import pymysql
    except Exception:
        return []
    connection = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USERNAME", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "litemall"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select t.id riskTaskId, t.review_id reviewId, t.risk_type riskType, t.status finalState,
                       t.handler reviewer, t.handle_note handleNote, a.workflow_trace_json workflowTraceJson
                from litemall_ai_review_risk_task t
                left join litemall_review_ai_analysis a on t.analysis_id = a.id
                order by t.id desc limit 100
                """
            )
            return list(cursor.fetchall())
    finally:
        connection.close()


def _check_row(row: dict[str, Any]) -> dict[str, Any]:
    snapshot = _governance(row)
    evidence = snapshot.get("evidenceCitations") or []
    human_note = str(row.get("handleNote") or "")
    issues = []
    if snapshot.get("decision") and not evidence and snapshot.get("evidenceStatus") != "supported":
        issues.append("missing_evidence")
    if not snapshot.get("reflectionReason"):
        issues.append("missing_reflection")
    if row.get("finalState") in {"closed", "ignored", "processed"} and not human_note:
        issues.append("missing_human_review")
    return {
        "reviewId": row.get("reviewId"),
        "riskTaskId": row.get("riskTaskId"),
        "workflowRoute": ((snapshot.get("process") or [{}])[0] or {}).get("name", ""),
        "riskTypes": snapshot.get("riskTypes") or [row.get("riskType")],
        "retrievalMode": _retrieval_mode(evidence),
        "evidenceCount": len(evidence),
        "reflectionStatus": snapshot.get("evidenceStatus", ""),
        "aiDecision": (snapshot.get("decision") or {}).get("code", ""),
        "humanDecision": _human_decision(human_note),
        "fallbackReason": _fallback_reason(snapshot),
        "finalState": row.get("finalState"),
        "linked": not issues,
        "issues": issues,
    }


def _governance(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("reviewGovernance") or row.get("review_governance")
    if isinstance(value, dict):
        return value
    trace_json = row.get("workflowTraceJson") or row.get("workflow_trace_json") or ""
    try:
        parsed = json.loads(trace_json) if isinstance(trace_json, str) else trace_json
        if isinstance(parsed, list):
            for item in reversed(parsed):
                if isinstance(item, dict):
                    snapshot = item.get("review_governance") or item.get("reviewGovernance")
                    if isinstance(snapshot, dict):
                        return snapshot
        if not isinstance(parsed, dict):
            return {}
        return parsed.get("review_governance") or parsed.get("reviewGovernance") or {}
    except Exception:
        return {}


def _retrieval_mode(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return "none"
    return str(((evidence[0] or {}).get("retrieval") or {}).get("mode") or "unknown")


def _human_decision(note: str) -> str:
    if "人工改判" in note or "override" in note:
        return "override"
    if "无需处置" in note or "no_action" in note:
        return "no_action"
    if "接受" in note or "accept_ai_suggestion" in note:
        return "accept_ai_suggestion"
    return ""


def _fallback_reason(snapshot: dict[str, Any]) -> str:
    for item in snapshot.get("failureReasons") or []:
        if isinstance(item, dict) and item.get("code") in {"RETRIEVAL_FAILED", "NO_EVIDENCE"}:
            return str(item.get("code"))
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
