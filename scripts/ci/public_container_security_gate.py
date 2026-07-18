from __future__ import annotations

import json
from pathlib import Path

from public_runtime_common import ROOT, main_guard


EVIDENCE = ROOT / "artifacts" / "operations" / "v1.9.0-phase3"
SCAN_DIR = EVIDENCE / "security"


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


def main() -> None:
    reports = sorted(SCAN_DIR.glob("*.json"))
    if not reports:
        raise RuntimeError("no Trivy JSON reports were produced")
    findings = []
    for report_path in reports:
        findings.extend(_find_critical_high(_load_json(report_path)))
    summary = {
        "reports": [str(path.relative_to(ROOT)) for path in reports],
        "criticalHighFindingCount": len(findings),
        "criticalHighFindings": findings,
        "exceptionDocument": "docs/security/PUBLIC_CONTAINER_RISK_EXCEPTIONS.md",
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "container-security-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if findings:
        raise SystemExit("PUBLIC_CONTAINER_SECURITY_BLOCKED: unexceptioned CRITICAL/HIGH findings present")
    print("PUBLIC_CONTAINER_SECURITY_PASS")


if __name__ == "__main__":
    main_guard(main)
