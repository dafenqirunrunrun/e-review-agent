from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE = ROOT / ".phase4a-baseline"
EXCEPTIONS_FILE = ROOT / "docs" / "security" / "public_container_risk_exceptions.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _report_context(path: Path, target: str) -> dict[str, str]:
    name = path.name
    if name == "filesystem.json":
        return {
            "targetType": "filesystem",
            "runtimeImage": "",
            "sourceModule": _source_module(target),
        }
    image = name.removesuffix(".json").replace("_", ":")
    return {
        "targetType": "image",
        "runtimeImage": image,
        "sourceModule": _source_module(target),
    }


def _source_module(target: str) -> str:
    if "litemall-admin" in target or "public-admin" in target:
        return "litemall-admin"
    if "litemall-vue" in target or "public-customer" in target:
        return "litemall-vue"
    if "ai-service" in target:
        return "ai-service"
    if "litemall" in target or "public-backend" in target:
        return "java-backend"
    if "alpine" in target:
        return "nginx-runtime"
    if "ubuntu" in target:
        return "java-runtime"
    return "repository"


def _package_manager(result: dict[str, Any]) -> str:
    class_name = str(result.get("Class") or "")
    type_name = str(result.get("Type") or "")
    if class_name:
        return f"{class_name}:{type_name}" if type_name else class_name
    return type_name


def _remediation_group(target: str, pkg_name: str) -> str:
    low_target = target.lower()
    low_pkg = pkg_name.lower()
    if "alpine" in low_target or "ubuntu" in low_target:
        return "A. Runtime OS packages"
    if low_pkg.startswith("com.fasterxml.jackson") or "jackson" in low_pkg:
        return "B. Java runtime dependencies"
    if low_pkg.startswith("ch.qos.logback") or "logback" in low_pkg:
        return "B. Java runtime dependencies"
    if low_pkg in {"setuptools", "pip", "wheel"} or "site-packages" in low_target:
        return "C. Python runtime dependencies"
    if "package-lock.json" in low_target:
        return "D. Frontend production dependencies"
    return "F. Duplicate exposure across source/image targets"


def _dependency_scope(result: dict[str, Any], target: str) -> str:
    if "package-lock.json" in target:
        return "direct-or-transitive-lockfile"
    if result.get("Class") == "os-pkgs":
        return "runtime-layer"
    return "unknown"


def _exception_map() -> dict[tuple[str, str, str, str], dict[str, Any]]:
    payload = _load_json(EXCEPTIONS_FILE)
    mapping: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for item in payload.get("exceptions") or []:
        key = (
            str(item.get("target") or ""),
            str(item.get("pkgName") or ""),
            str(item.get("vulnerabilityId") or ""),
            str(item.get("installedVersion") or ""),
        )
        mapping[key] = item
    return mapping


def build_inventory(baseline_dir: Path = DEFAULT_BASELINE) -> list[dict[str, Any]]:
    exceptions = _exception_map()
    rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for report_path in sorted((baseline_dir / "security").glob("*.json")):
        report = _load_json(report_path)
        for result in report.get("Results") or []:
            target = str(result.get("Target") or "")
            context = _report_context(report_path, target)
            for vuln in result.get("Vulnerabilities") or []:
                severity = str(vuln.get("Severity") or "").upper()
                if severity != "CRITICAL":
                    continue
                pkg_name = str(vuln.get("PkgName") or "")
                vuln_id = str(vuln.get("VulnerabilityID") or "")
                installed = str(vuln.get("InstalledVersion") or "")
                key = (target, pkg_name, vuln_id, installed)
                exception = exceptions.get(key)
                rows[key] = {
                    "scanReport": str(report_path.relative_to(baseline_dir)),
                    "target": target,
                    "targetType": context["targetType"],
                    "packageManager": _package_manager(result),
                    "pkgName": pkg_name,
                    "vulnerabilityId": vuln_id,
                    "severity": severity,
                    "installedVersion": installed,
                    "fixedVersion": str(vuln.get("FixedVersion") or ""),
                    "runtimeImage": context["runtimeImage"],
                    "sourceModule": context["sourceModule"],
                    "directOrTransitive": _dependency_scope(result, target),
                    "reachability": str((exception or {}).get("reachability") or "unknown"),
                    "currentException": bool(exception),
                    "remediationGroup": _remediation_group(target, pkg_name),
                }
    return list(rows.values())


def main() -> None:
    rows = build_inventory()
    DEFAULT_BASELINE.mkdir(parents=True, exist_ok=True)
    (DEFAULT_BASELINE / "critical-inventory.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    fields = [
        "scanReport",
        "target",
        "targetType",
        "packageManager",
        "pkgName",
        "vulnerabilityId",
        "severity",
        "installedVersion",
        "fixedVersion",
        "runtimeImage",
        "sourceModule",
        "directOrTransitive",
        "reachability",
        "currentException",
        "remediationGroup",
    ]
    with (DEFAULT_BASELINE / "critical-inventory.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"critical count = {len(rows)}")


if __name__ == "__main__":
    main()
