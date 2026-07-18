from __future__ import annotations

import json
from pathlib import Path

from public_runtime_common import ROOT, main_guard


EVIDENCE = ROOT / "artifacts" / "operations" / "v1.9.0-phase3"
SCAN_DIR = EVIDENCE / "security"
EXCEPTIONS_FILE = ROOT / "docs" / "security" / "public_container_risk_exceptions.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"missing scan output: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _find_critical_high(report: dict) -> list[dict]:
    findings = []
    for result in report.get("Results") or []:
        for vuln in result.get("Vulnerabilities") or []:
            severity = str(vuln.get("Severity") or "").upper()
            if severity in {"CRITICAL", "HIGH"}:
                findings.append({
                    "target": result.get("Target"),
                    "vulnerabilityId": vuln.get("VulnerabilityID"),
                    "pkgName": vuln.get("PkgName"),
                    "installedVersion": vuln.get("InstalledVersion"),
                    "fixedVersion": vuln.get("FixedVersion"),
                    "severity": severity,
                })
    return findings


def _exception_key(finding: dict) -> tuple[str, str, str]:
    return (
        str(finding.get("target") or ""),
        str(finding.get("pkgName") or ""),
        str(finding.get("vulnerabilityId") or ""),
    )


def _load_exceptions() -> set[tuple[str, str, str]]:
    if not EXCEPTIONS_FILE.exists():
        return set()
    payload = json.loads(EXCEPTIONS_FILE.read_text(encoding="utf-8"))
    exceptions = set()
    for item in payload.get("exceptions") or []:
        exceptions.add((
            str(item.get("target") or ""),
            str(item.get("pkgName") or ""),
            str(item.get("vulnerabilityId") or ""),
        ))
    return exceptions


def main() -> None:
    reports = sorted(SCAN_DIR.glob("*.json"))
    if not reports:
        raise RuntimeError("no Trivy JSON reports were produced")
    exceptions = _load_exceptions()
    findings = []
    exception_count = 0
    for report_path in reports:
        for finding in _find_critical_high(_load_json(report_path)):
            if _exception_key(finding) in exceptions:
                exception_count += 1
            else:
                findings.append(finding)
    summary = {
        "reports": [str(path.relative_to(ROOT)) for path in reports],
        "criticalHighFindingCount": len(findings) + exception_count,
        "exceptionedCriticalHighFindingCount": exception_count,
        "unexceptionedCriticalHighFindingCount": len(findings),
        "unexceptionedCriticalHighFindings": findings,
        "exceptionDocument": "docs/security/PUBLIC_CONTAINER_RISK_EXCEPTIONS.md",
        "exceptionData": "docs/security/public_container_risk_exceptions.json",
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "container-security-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if findings:
        raise SystemExit("PUBLIC_CONTAINER_SECURITY_BLOCKED: unexceptioned CRITICAL/HIGH findings present")
    print("PUBLIC_CONTAINER_SECURITY_PASS")


if __name__ == "__main__":
    main_guard(main)
