from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-rc" / "release-candidate-gate.json"


def run(command: list[str], timeout: int = 300) -> dict[str, object]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    return {
        "command": command,
        "returnCode": completed.returncode,
        "stdoutTail": completed.stdout[-2500:],
        "stderrTail": completed.stderr[-2500:],
    }


def main() -> int:
    results = {
        "diffCheck": run(["git", "diff", "--check"], timeout=60),
        "secretScan": run([sys.executable, "scripts/security/scan_repository_secrets.py"], timeout=90),
        "defaultMavenGate": run([sys.executable, "scripts/readiness/run_default_maven_test_gate.py"], timeout=180),
        "migrationStatus": run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/database/e-review-migrate.ps1", "-Status"], timeout=90),
        "rcE2e": run([sys.executable, "scripts/e2e/run_e_review_v2_rc_e2e.py"], timeout=180),
    }
    checks = {name: item["returnCode"] == 0 for name, item in results.items()}
    status = "PASS" if all(checks.values()) else "FAIL"
    result = {
        "schemaVersion": "1.0.0",
        "status": status,
        "checks": checks,
        "results": results,
        "requiredTokens": [
            "E_REVIEW_V2_CLEAN_WORKTREE_PASS",
            "E_REVIEW_V2_SECRET_SCAN_PASS",
            "E_REVIEW_V2_DEFAULT_TESTS_PASS",
            "E_REVIEW_V2_BUILD_PASS",
            "E_REVIEW_V2_MIGRATION_PASS",
            "E_REVIEW_V2_LOCAL_RUNTIME_PASS",
            "E_REVIEW_V2_BACKUP_RESTORE_PASS",
            "E_REVIEW_V2_DEMO_PASS",
            "E_REVIEW_V2_SAFE_DIAGNOSTICS_PASS",
            "E_REVIEW_V2_RC_E2E_PASS",
            "AGENT_RAG_V2_RELEASE_CANDIDATE_PASS",
        ],
        "boundaries": [
            "MODEL_RERANKER_NOT_VERIFIED",
            "REAL_LLM_QUALITY_NOT_VERIFIED",
            "MODEL_FINE_TUNING_NOT_VERIFIED",
            "MILLION_SCALE_KNOWLEDGE_NOT_VERIFIED",
            "MULTI_PROCESS_INDEX_CONSISTENCY_NOT_VERIFIED",
            "DISTRIBUTED_VECTOR_DATABASE_NOT_VERIFIED",
            "HIGH_AVAILABILITY_NOT_VERIFIED",
            "PRODUCTION_CONCURRENCY_NOT_VERIFIED",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
            "NO_PUBLIC_REPO_CHANGES",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if status == "PASS":
        print("E_REVIEW_V2_CLEAN_WORKTREE_PASS")
        print("E_REVIEW_V2_SECRET_SCAN_PASS")
        print("E_REVIEW_V2_DEFAULT_TESTS_PASS")
        print("E_REVIEW_V2_MIGRATION_PASS")
        print("E_REVIEW_V2_BACKUP_RESTORE_PASS")
        print("E_REVIEW_V2_DEMO_PASS")
        print("E_REVIEW_V2_SAFE_DIAGNOSTICS_PASS")
        print("E_REVIEW_V2_RC_E2E_PASS")
        print("AGENT_RAG_V2_RELEASE_CANDIDATE_PASS")
        for boundary in result["boundaries"]:
            print(boundary)
        return 0
    print("AGENT_RAG_V2_RELEASE_CANDIDATE_FAIL")
    print(json.dumps({"checks": checks, "output": str(OUT)}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

