from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any

from public_runtime_common import ROOT, main_guard


EVIDENCE = ROOT / "artifacts" / "operations" / "v1.9.0-phase3"
SCAN_DIR = EVIDENCE / "security"
EXCEPTIONS_FILE = ROOT / "docs" / "security" / "public_container_risk_exceptions.json"
REQUIRED_FIELDS = {
    "target",
    "pkgName",
    "vulnerabilityId",
    "severity",
    "installedVersion",
    "fixedVersion",
    "reason",
    "remediation",
    "owner",
    "trackingIssue",
    "createdAt",
    "expires",
    "disposition",
    "reachability",
}
DISPOSITIONS = {"accepted-temporarily", "not-applicable", "false-positive"}
REACHABILITY = {"reachable", "not-reachable", "unknown"}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"missing or empty scan output: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _source_commit() -> str:
    return os.getenv("GITHUB_SHA") or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()


def _today() -> date:
    override = os.getenv("PUBLIC_SECURITY_GATE_TODAY")
    if override:
        return _parse_date(override, "PUBLIC_SECURITY_GATE_TODAY")
    return date.today()


def _parse_date(value: str, label: str) -> date:
    if not DATE_PATTERN.match(value or ""):
        raise ValueError(f"{label} must use YYYY-MM-DD")
    return datetime.strptime(value, "%Y-%m-%d").date()


def _finding_key(finding: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(finding.get("target") or ""),
        str(finding.get("pkgName") or ""),
        str(finding.get("vulnerabilityId") or ""),
        str(finding.get("severity") or "").upper(),
        str(finding.get("installedVersion") or ""),
    )


def _exception_key(exception: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(exception.get("target") or ""),
        str(exception.get("pkgName") or ""),
        str(exception.get("vulnerabilityId") or ""),
        str(exception.get("severity") or "").upper(),
        str(exception.get("installedVersion") or ""),
    )


def _scan_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for result in report.get("Results") or []:
        target = result.get("Target")
        for vuln in result.get("Vulnerabilities") or []:
            severity = str(vuln.get("Severity") or "").upper()
            if severity in {"CRITICAL", "HIGH"}:
                findings.append({
                    "target": target,
                    "vulnerabilityId": vuln.get("VulnerabilityID"),
                    "pkgName": vuln.get("PkgName"),
                    "installedVersion": vuln.get("InstalledVersion"),
                    "fixedVersion": vuln.get("FixedVersion"),
                    "severity": severity,
                })
    return findings


def _load_scan_findings() -> tuple[list[Path], list[dict[str, Any]]]:
    reports = sorted(SCAN_DIR.glob("*.json"))
    if not reports:
        raise RuntimeError("no Trivy JSON reports were produced")
    findings: list[dict[str, Any]] = []
    for report_path in reports:
        findings.extend(_scan_findings(_load_json(report_path)))
    return reports, findings


def _report_metadata(reports: list[Path]) -> dict[str, Any]:
    trivy_versions = set()
    created_at = {}
    database_updated_at = set()
    database_next_update = set()
    for report_path in reports:
        report = _load_json(report_path)
        trivy_version = (report.get("Trivy") or {}).get("Version")
        if trivy_version:
            trivy_versions.add(trivy_version)
        if report.get("CreatedAt"):
            created_at[str(report_path.relative_to(ROOT))] = report.get("CreatedAt")
        db = ((report.get("Metadata") or {}).get("DB") or {})
        if db.get("UpdatedAt"):
            database_updated_at.add(db["UpdatedAt"])
        if db.get("NextUpdate"):
            database_next_update.add(db["NextUpdate"])
    return {
        "trivyVersions": sorted(trivy_versions),
        "scanCreatedAt": created_at,
        "databaseUpdatedAt": sorted(database_updated_at),
        "databaseNextUpdate": sorted(database_next_update),
    }


def _validate_exception_schema(exceptions: list[dict[str, Any]], finding_keys: set[tuple[str, str, str, str, str]]) -> dict[str, Any]:
    today = _today()
    invalid: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []
    orphan: list[dict[str, Any]] = []
    duplicate: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()

    for index, item in enumerate(exceptions):
        key = _exception_key(item)
        missing = sorted(field for field in REQUIRED_FIELDS if field not in item or str(item.get(field) or "").strip() == "")
        errors = []
        if missing:
            errors.append("missing fields: " + ", ".join(missing))
        if key in seen:
            duplicate.append({"index": index, "key": key})
            errors.append("duplicate exception")
        seen.add(key)
        if key not in finding_keys:
            orphan.append({"index": index, "key": key})
            errors.append("exception does not match current scan finding")
        if str(item.get("disposition") or "") not in DISPOSITIONS:
            errors.append("invalid disposition")
        if str(item.get("reachability") or "") not in REACHABILITY:
            errors.append("invalid reachability")
        if item.get("severity") == "CRITICAL" and not str(item.get("criticalRiskStatement") or "").strip():
            errors.append("CRITICAL exception requires criticalRiskStatement")
        try:
            created_at = _parse_date(str(item.get("createdAt") or ""), "createdAt")
            expires = _parse_date(str(item.get("expires") or ""), "expires")
            if created_at > today:
                errors.append("createdAt is in the future")
            if expires < today:
                expired.append({"index": index, "key": key})
                errors.append("exception is expired")
            if (expires - created_at).days > 90 and not str(item.get("longTermExceptionReason") or "").strip():
                errors.append("exception exceeds 90 days without longTermExceptionReason")
        except ValueError as exc:
            errors.append(str(exc))
        if errors:
            invalid.append({"index": index, "key": key, "errors": errors})

    stale_count = len(orphan)
    return {
        "invalid": invalid,
        "expired": expired,
        "duplicate": duplicate,
        "orphan": orphan,
        "staleExceptionCount": stale_count,
        "validKeys": seen,
    }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    reports, findings = _load_scan_findings()
    report_metadata = _report_metadata(reports)
    finding_keys = {_finding_key(finding) for finding in findings}
    payload = _load_json(EXCEPTIONS_FILE)
    exceptions = payload.get("exceptions")
    if not isinstance(exceptions, list):
        raise RuntimeError("exceptions must be a list")

    validation = _validate_exception_schema(exceptions, finding_keys)
    exception_keys = validation["validKeys"]
    exceptioned = [finding for finding in findings if _finding_key(finding) in exception_keys]
    unexceptioned = [finding for finding in findings if _finding_key(finding) not in exception_keys]

    critical_count = sum(1 for finding in findings if finding["severity"] == "CRITICAL")
    high_count = sum(1 for finding in findings if finding["severity"] == "HIGH")
    exceptioned_critical = sum(1 for finding in exceptioned if finding["severity"] == "CRITICAL")
    exceptioned_high = sum(1 for finding in exceptioned if finding["severity"] == "HIGH")
    unexceptioned_critical = sum(1 for finding in unexceptioned if finding["severity"] == "CRITICAL")
    unexceptioned_high = sum(1 for finding in unexceptioned if finding["severity"] == "HIGH")
    invalid_count = len(validation["invalid"])
    expired_count = len(validation["expired"])
    orphan_count = len(validation["orphan"])
    release_security_blocked = bool(critical_count or exceptioned_high or unexceptioned_high or expired_count or invalid_count)

    summary = {
        "schemaVersion": "public-container-security-gate-v2",
        "sourceCommit": _source_commit(),
        "workflowRunId": os.getenv("GITHUB_RUN_ID", "local"),
        "generatedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "status": "BLOCKED" if release_security_blocked else "PASS",
        "scanCompleted": True,
        "scanReportCount": len(reports),
        "trivyVersions": report_metadata["trivyVersions"],
        "scanCreatedAt": report_metadata["scanCreatedAt"],
        "databaseUpdatedAt": report_metadata["databaseUpdatedAt"],
        "databaseNextUpdate": report_metadata["databaseNextUpdate"],
        "scanReportSha256": {str(path.relative_to(ROOT)): _sha256(path) for path in reports},
        "criticalFindingCount": critical_count,
        "highFindingCount": high_count,
        "exceptionSchemaValid": invalid_count == 0,
        "exceptionedCriticalCount": exceptioned_critical,
        "exceptionedHighCount": exceptioned_high,
        "unexceptionedCriticalCount": unexceptioned_critical,
        "unexceptionedHighCount": unexceptioned_high,
        "expiredExceptionCount": expired_count,
        "invalidExceptionCount": invalid_count,
        "staleExceptionCount": validation["staleExceptionCount"],
        "orphanExceptionCount": orphan_count,
        "duplicateExceptionCount": len(validation["duplicate"]),
        "releaseSecurityBlocked": release_security_blocked,
        "unfixedVulnerabilitiesExcluded": True,
        "checks": {
            "scanCompleted": True,
            "exceptionSchemaValid": invalid_count == 0,
            "expiredExceptionCount": expired_count,
            "unexceptionedCriticalCount": unexceptioned_critical,
            "unexceptionedHighCount": unexceptioned_high,
            "releaseSecurityBlocked": release_security_blocked,
        },
        "boundaries": [
            "PUBLIC_RELEASE_SECURITY_BLOCKED" if release_security_blocked else "PUBLIC_RELEASE_SECURITY_UNBLOCKED",
            "PRODUCTION_READY_NOT_CLAIMED",
        ],
        "unexceptionedFindings": unexceptioned,
        "invalidExceptions": validation["invalid"],
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "container-security-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if invalid_count or expired_count or orphan_count or unexceptioned:
        print("PUBLIC_CONTAINER_RISK_BASELINE_INVALID")
        raise SystemExit("PUBLIC_CONTAINER_SECURITY_BLOCKED: invalid, expired, orphan or unexceptioned findings present")
    print("PUBLIC_CONTAINER_RISK_BASELINE_AUDITED")
    print("PUBLIC_CONTAINER_EXCEPTIONS_VALIDATED")
    if release_security_blocked:
        print("PUBLIC_RELEASE_SECURITY_BLOCKED")
    elif critical_count == 0 and exceptioned_high == 0:
        print("PUBLIC_CONTAINER_SECURITY_PASS")
    elif critical_count == 0:
        print("PUBLIC_CONTAINER_SECURITY_PASS_WITH_EXCEPTIONS")


if __name__ == "__main__":
    main_guard(main)
