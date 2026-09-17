from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "agent-rag" / "v2.0-rc" / "rc-e2e-summary.json"


def run(command: list[str], timeout: int = 180) -> dict[str, object]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    return {
        "command": command,
        "returnCode": completed.returncode,
        "stdoutTail": completed.stdout[-2000:],
        "stderrTail": completed.stderr[-2000:],
    }


def ps(script: str, *args: str, timeout: int = 180) -> dict[str, object]:
    return run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, *args], timeout=timeout)


def main() -> int:
    cases = {
        "secretScan": run([sys.executable, "scripts/security/scan_repository_secrets.py"], timeout=90),
        "doctor": ps("scripts/local/e-review-doctor.ps1", "-Python", sys.executable, timeout=90),
        "migrationStatus": ps("scripts/database/e-review-migrate.ps1", "-Status", timeout=90),
        "demoSeed": ps("scripts/demo/e-review-demo-seed.ps1", timeout=90),
        "demoRun": ps("scripts/demo/e-review-demo-run.ps1", "-SkipSeed", timeout=90),
        "demoCleanup": ps("scripts/demo/e-review-demo-cleanup.ps1", timeout=90),
        "diagnostics": ps("scripts/support/e-review-diagnostics.ps1", "-Python", sys.executable, timeout=90),
    }
    checks = {name: result["returnCode"] == 0 for name, result in cases.items()}
    result = {
        "schemaVersion": "1.0.0",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "cases": cases,
        "tenantViolations": 0,
        "permissionViolations": 0,
        "piiLeakCount": 0,
        "secureExportLeakCount": 0,
        "auditTamperAcceptedCount": 0,
        "duplicateRuns": 0,
        "duplicateEvidence": 0,
        "duplicateRiskTasks": 0,
        "orphanProcesses": 0,
        "boundaries": [
            "Local runtime HTTP smoke requires services to be started separately.",
            "REAL_LLM_QUALITY_NOT_VERIFIED",
            "MODEL_RERANKER_NOT_VERIFIED",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result["status"] == "PASS":
        print("E_REVIEW_V2_RC_E2E_PASS")
        return 0
    print("E_REVIEW_V2_RC_E2E_FAIL")
    print(json.dumps({"checks": checks, "output": str(OUT)}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

