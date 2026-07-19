from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from public_container_security_gate import _exception_key, _finding_key, _load_json, _load_scan_findings, _validate_exception_schema
from public_runtime_common import ROOT, main_guard


EVIDENCE = ROOT / "artifacts" / "operations" / "v1.9.0-phase4a"
BASELINE_EXCEPTIONS_FILE = ROOT / "docs" / "security" / "public_container_risk_exceptions.json"


def _source_commit() -> str:
    return os.getenv("GITHUB_SHA") or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()


def _high_keys_from_exceptions(exceptions: list[dict[str, Any]]) -> set[tuple[str, str, str, str, str]]:
    return {_exception_key(item) for item in exceptions if str(item.get("severity") or "").upper() == "HIGH"}


def main() -> None:
    reports, findings = _load_scan_findings()
    finding_keys = {_finding_key(finding) for finding in findings}
    exception_payload = _load_json(BASELINE_EXCEPTIONS_FILE)
    exceptions = exception_payload.get("exceptions")
    if not isinstance(exceptions, list):
        raise RuntimeError("exceptions must be a list")
    validation = _validate_exception_schema(exceptions, finding_keys)

    critical_findings = [finding for finding in findings if finding["severity"] == "CRITICAL"]
    high_findings = [finding for finding in findings if finding["severity"] == "HIGH"]
    high_baseline_keys = _high_keys_from_exceptions(exceptions)
    new_high_findings = [finding for finding in high_findings if _finding_key(finding) not in high_baseline_keys]
    critical_exceptions = [item for item in exceptions if str(item.get("severity") or "").upper() == "CRITICAL"]

    summary = {
        "schemaVersion": "public-critical-zero-phase4a-v1",
        "sourceCommit": _source_commit(),
        "workflowRunId": os.getenv("GITHUB_RUN_ID", "local"),
        "generatedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "status": "PASS" if not critical_findings and not critical_exceptions and not new_high_findings and not validation["invalid"] and not validation["expired"] and not validation["orphan"] and not validation["duplicate"] else "BLOCKED",
        "scanReportCount": len(reports),
        "criticalFindingCount": len(critical_findings),
        "criticalExceptionCount": len(critical_exceptions),
        "highFindingCount": len(high_findings),
        "newHighFindingCount": len(new_high_findings),
        "invalidExceptionCount": len(validation["invalid"]),
        "expiredExceptionCount": len(validation["expired"]),
        "duplicateExceptionCount": len(validation["duplicate"]),
        "orphanExceptionCount": len(validation["orphan"]),
        "checks": {
            "scanReportCountAtLeastFive": len(reports) >= 5,
            "criticalFindingCountZero": len(critical_findings) == 0,
            "criticalExceptionCountZero": len(critical_exceptions) == 0,
            "newHighFindingCountZero": len(new_high_findings) == 0,
            "exceptionSchemaValid": not validation["invalid"],
            "expiredExceptionCountZero": not validation["expired"],
            "duplicateExceptionCountZero": not validation["duplicate"],
            "orphanExceptionCountZero": not validation["orphan"],
        },
        "boundaries": [
            "PUBLIC_HIGH_RISK_BASELINE_REMAINS",
            "PUBLIC_RELEASE_SECURITY_BLOCKED",
            "PRODUCTION_READY_NOT_CLAIMED",
        ],
        "criticalFindings": critical_findings,
        "criticalExceptions": critical_exceptions,
        "newHighFindings": new_high_findings,
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "critical-zero-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if len(reports) < 5:
        raise SystemExit("PUBLIC_CRITICAL_ZERO_BLOCKED: scanReportCount < 5")
    if summary["status"] != "PASS":
        raise SystemExit("PUBLIC_CRITICAL_ZERO_BLOCKED")
    print("PUBLIC_CRITICAL_VULNERABILITIES_ZERO")
    print("PUBLIC_CRITICAL_EXCEPTIONS_ZERO")
    print("PUBLIC_CRITICAL_ZERO_PHASE4A_PASS")
    print("PUBLIC_HIGH_RISK_BASELINE_REMAINS")
    print("PUBLIC_RELEASE_SECURITY_BLOCKED")
    print("PRODUCTION_READY_NOT_CLAIMED")


if __name__ == "__main__":
    main_guard(main)
