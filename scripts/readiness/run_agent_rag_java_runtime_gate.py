from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUMMARY_DIR = ROOT / "artifacts" / "agent-rag" / "v2.0-java-runtime"
OUT = SUMMARY_DIR / "java-runtime-gate-summary.json"


REQUIRED = {
    "database": SUMMARY_DIR / "database-migration-summary.json",
    "aiRuntime": SUMMARY_DIR / "ai-runtime-summary.json",
    "adminRuntime": SUMMARY_DIR / "admin-runtime-summary.json",
    "workflow": SUMMARY_DIR / "java-workflow-runtime-summary.json",
}


TOKENS = [
    "AGENT_RAG_DATABASE_MIGRATION_PASS",
    "AGENT_RAG_AI_RUNTIME_PASS",
    "AGENT_RAG_ADMIN_API_RUNTIME_PASS",
    "AGENT_RAG_JAVA_HTTP_INTEGRATION_PASS",
    "AGENT_RAG_RUNTIME_PERSISTENCE_PASS",
    "AGENT_RAG_RUNTIME_IDEMPOTENCY_PASS",
    "AGENT_RAG_RUNTIME_OVERRIDE_PASS",
    "AGENT_RAG_RUNTIME_REPLAY_PASS",
    "AGENT_RAG_RUNTIME_CIRCUIT_BREAKER_PASS",
    "AGENT_RAG_JAVA_WORKFLOW_RUNTIME_PASS",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-dir", default=str(SUMMARY_DIR))
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()

    summary_dir = Path(args.summary_dir)
    files = {name: summary_dir / path.name for name, path in REQUIRED.items()}
    result = {
        "schemaVersion": "1.0.0",
        "status": "FAIL",
        "summaryDir": str(summary_dir.relative_to(ROOT)) if summary_dir.is_relative_to(ROOT) else "[external]",
        "checks": {},
        "missing": [],
    }

    loaded: dict[str, dict] = {}
    for name, path in files.items():
        if not path.exists():
            result["missing"].append(f"file:{path.name}")
            loaded[name] = {}
            continue
        loaded[name] = json.loads(path.read_text(encoding="utf-8-sig"))

    check_status(result, "database.pass", loaded["database"].get("status") == "PASS")
    check_status(result, "aiRuntime.pass", loaded["aiRuntime"].get("status") == "PASS")
    check_status(result, "adminRuntime.pass", loaded["adminRuntime"].get("status") == "PASS")
    check_status(result, "workflow.pass", loaded["workflow"].get("status") == "PASS")

    workflow = loaded["workflow"]
    check_status(result, "tenantViolations.zero", int(workflow.get("tenantViolations", -1)) == 0)
    check_status(result, "duplicateRuns.zero", int(workflow.get("duplicateRuns", -1)) == 0)
    check_status(result, "duplicateEvidence.zero", int(workflow.get("duplicateEvidence", -1)) == 0)
    check_status(result, "duplicateRiskTasks.zero", int(workflow.get("duplicateRiskTasks", -1)) == 0)
    check_status(result, "overridePreservedOriginal", workflow.get("overridePreservedOriginal") is True)
    check_status(result, "replayCreatedNewRun", workflow.get("replayCreatedNewRun") is True)
    check_status(result, "circuitBreakerOpened", workflow.get("circuitBreakerOpened") is True)
    check_status(result, "circuitBreakerRecovered", workflow.get("circuitBreakerRecovered") is True)

    result["status"] = "PASS" if not result["missing"] else "FAIL"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if result["status"] == "PASS":
        for token in TOKENS:
            print(token)
        return 0
    print("AGENT_RAG_JAVA_WORKFLOW_RUNTIME_FAIL")
    print(json.dumps({"missing": result["missing"]}, ensure_ascii=False))
    return 1


def check_status(result: dict, name: str, passed: bool) -> None:
    result["checks"][name] = passed
    if not passed:
        result["missing"].append(name)


if __name__ == "__main__":
    raise SystemExit(main())
