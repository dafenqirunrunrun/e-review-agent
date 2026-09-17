from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-java-runtime" / "database-migration-summary.json"


REQUIRED_TABLES = {
    "litemall_agent_rag_run": {
        "columns": {"request_id", "idempotency_key", "tenant_id", "subject_type", "subject_id", "status", "created_at"},
        "unique": {"uk_agent_rag_run_tenant_request", "uk_agent_rag_run_idem"},
        "indexes": {"idx_agent_rag_run_subject", "idx_agent_rag_run_status_time", "idx_agent_rag_run_risk_time"},
    },
    "litemall_agent_rag_evidence": {
        "columns": {"evidence_id", "run_id", "tenant_id", "bundle_hash", "bounded_json", "payload_size_bytes"},
        "unique": {"uk_agent_rag_evidence_run", "uk_agent_rag_evidence_tenant_id"},
        "indexes": {"idx_agent_rag_evidence_request"},
    },
    "litemall_agent_rag_override": {
        "columns": {"run_id", "tenant_id", "new_risk_level", "new_action", "reason", "operator_id"},
        "unique": set(),
        "indexes": {"idx_agent_rag_override_run_time", "idx_agent_rag_override_tenant_time"},
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mysql", default=os.environ.get("MYSQL_BIN", "mysql"))
    parser.add_argument("--host", default=os.environ.get("MYSQL_HOST", "localhost"))
    parser.add_argument("--port", default=os.environ.get("MYSQL_PORT", "3306"))
    parser.add_argument("--user", default=os.environ.get("MYSQL_USER", "litemall"))
    parser.add_argument("--database", default=os.environ.get("MYSQL_DATABASE", "litemall"))
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()

    if not os.environ.get("MYSQL_PWD"):
        print("MYSQL_PWD is required but is not written to output.", file=sys.stderr)
        return 2

    result = {
        "schemaVersion": "1.0.0",
        "status": "FAIL",
        "database": args.database,
        "tables": [],
        "uniqueConstraints": [],
        "indexes": [],
        "missing": [],
        "migrationApplied": False,
    }

    try:
        tables = set(query(args, "SHOW TABLES LIKE '%agent_rag%';"))
        result["tables"] = sorted(tables)
        for table, required in REQUIRED_TABLES.items():
            if table not in tables:
                result["missing"].append(f"table:{table}")
                continue
            columns = set(query(args, f"SHOW COLUMNS FROM {table};", first_column=True))
            missing_columns = sorted(required["columns"] - columns)
            result["missing"].extend([f"column:{table}.{name}" for name in missing_columns])
            index_names = set(query(args, f"SHOW INDEX FROM {table};", first_column=False, column_index=2))
            unique_names = set(query(args, f"SHOW INDEX FROM {table} WHERE Non_unique = 0;", first_column=False, column_index=2))
            result["indexes"].extend(sorted(index_names))
            result["uniqueConstraints"].extend(sorted(unique_names))
            result["missing"].extend([f"unique:{table}.{name}" for name in sorted(required["unique"] - unique_names)])
            result["missing"].extend([f"index:{table}.{name}" for name in sorted(required["indexes"] - index_names)])
        result["indexes"] = sorted(set(result["indexes"]))
        result["uniqueConstraints"] = sorted(set(result["uniqueConstraints"]))
        result["migrationApplied"] = not result["missing"]
        result["status"] = "PASS" if result["migrationApplied"] else "FAIL"
    except Exception as exc:  # pragma: no cover - gate diagnostics
        result["missing"].append(f"query-error:{exc}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result["status"] == "PASS":
        print("AGENT_RAG_DATABASE_MIGRATION_PASS")
        return 0
    print("AGENT_RAG_DATABASE_MIGRATION_FAIL")
    print(json.dumps({"missing": result["missing"]}, ensure_ascii=False))
    return 1


def query(args, sql: str, *, first_column: bool = True, column_index: int = 0) -> list[str]:
    cmd = [
        args.mysql,
        "-h",
        args.host,
        "-P",
        str(args.port),
        "-u",
        args.user,
        "-N",
        "-B",
        args.database,
        "-e",
        sql,
    ]
    completed = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    rows = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        rows.append(parts[0 if first_column else column_index])
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
