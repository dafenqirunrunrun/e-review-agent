from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "artifacts" / "operations" / "v1.9.0-phase3"
RUNTIME_EVIDENCE = ROOT / "artifacts" / "runtime" / "v1.9.0-phase2"


def _source_commit() -> str:
    return os.getenv("GITHUB_SHA") or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()


def _load(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"missing or empty evidence file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key in ["schemaVersion", "sourceCommit", "workflowRunId", "generatedAt", "status", "checks", "boundaries"]:
        if key not in payload:
            raise RuntimeError(f"evidence missing {key}: {path}")
    return payload


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _validate_observability() -> dict[str, Any]:
    payload = _load(RUNTIME_EVIDENCE / "observability-smoke-summary.json")
    _require(payload["status"] == "PASS", "observability status must be PASS")
    _require(payload.get("requestIdPropagation") is True, "observability requestIdPropagation must be true")
    _require(payload.get("metricsVerified") is True, "observability metricsVerified must be true")
    return payload


def _validate_probe_restore() -> dict[str, Any]:
    payload = _load(RUNTIME_EVIDENCE / "backup-restore-smoke-summary.json")
    _require(payload["status"] == "PASS", "probe restore status must be PASS")
    _require(payload.get("restored") is True, "probe restore restored must be true")
    _require(payload.get("scope") == "single-probe-table", "probe restore scope must be single-probe-table")
    _require(payload.get("cleanVolumeRestore") is False, "probe restore must not claim clean volume restore")
    _require(payload.get("businessTablesVerified") is False, "probe restore must not claim business table verification")
    return payload


def _validate_container_risk() -> dict[str, Any]:
    payload = _load(EVIDENCE / "container-security-summary.json")
    _require(payload.get("scanCompleted") is True, "container scanCompleted must be true")
    _require(payload.get("exceptionSchemaValid") is True, "exceptionSchemaValid must be true")
    _require(payload.get("expiredExceptionCount") == 0, "expiredExceptionCount must be zero")
    _require(payload.get("unexceptionedCriticalCount") == 0, "unexceptionedCriticalCount must be zero")
    _require(payload.get("unexceptionedHighCount") == 0, "unexceptionedHighCount must be zero")
    has_critical_or_high_exceptions = bool(
        payload.get("exceptionedCriticalCount", 0) or payload.get("exceptionedHighCount", 0)
    )
    if has_critical_or_high_exceptions:
        _require(payload.get("releaseSecurityBlocked") is True, "releaseSecurityBlocked must remain true while CRITICAL/HIGH exceptions exist")
    return payload


def _validate_sbom() -> dict[str, Any]:
    manifest = _load(EVIDENCE / "sbom" / "manifest.json")
    _require(manifest.get("tool") == "trivy", "SBOM tool must be trivy")
    _require(bool(manifest.get("toolVersion")), "SBOM toolVersion is required")
    images = manifest.get("images") or {}
    _require(set(images.keys()) == {"backend", "ai-service", "admin", "customer"}, "SBOM must include four public runtime images")
    for name, item in images.items():
        for key in ["image", "imageDigest", "sbomPath", "sbomSha256"]:
            _require(bool(item.get(key)), f"SBOM {name} missing {key}")
        _require(str(item["imageDigest"]).startswith("sha256:"), f"SBOM {name} imageDigest must be sha256")
        sbom_path = ROOT / item["sbomPath"]
        _require(sbom_path.exists() and sbom_path.stat().st_size > 0, f"SBOM file missing or empty: {sbom_path}")
        json.loads(sbom_path.read_text(encoding="utf-8"))
    return manifest


def _validate_restart_recovery() -> dict[str, Any]:
    payload = _load(RUNTIME_EVIDENCE / "rollback-smoke-summary.json")
    _require(payload["status"] == "PASS", "restart recovery status must be PASS")
    _require(payload.get("mode") == "compose-service-restart", "restart recovery mode must be compose-service-restart")
    _require(payload.get("applicationVersionRollback") is False, "restart recovery must not claim application rollback")
    return payload


def main() -> None:
    results = {
        "observability": _validate_observability(),
        "mysqlLogicalProbeRestore": _validate_probe_restore(),
        "containerRiskBaseline": _validate_container_risk(),
        "sbom": _validate_sbom(),
        "backendRestartRecovery": _validate_restart_recovery(),
    }
    release_security_blocked = results["containerRiskBaseline"].get("releaseSecurityBlocked") is True
    final_status = "PARTIAL" if release_security_blocked else "PASS"
    gate_result = {
        "schemaVersion": "public-operations-phase3-gate-v2",
        "sourceCommit": _source_commit(),
        "workflowRunId": os.getenv("GITHUB_RUN_ID", "local"),
        "generatedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "status": final_status,
        "checks": {
            "observability": "PASS",
            "mysqlLogicalProbeRestore": "PASS",
            "containerRiskBaseline": "BLOCKED" if release_security_blocked else "PASS",
            "sbom": "PASS",
            "backendRestartRecovery": "PASS",
        },
        "boundaries": [
            "PUBLIC_RELEASE_SECURITY_BLOCKED" if release_security_blocked else "PUBLIC_RELEASE_SECURITY_UNBLOCKED",
            "PRODUCTION_READY_NOT_CLAIMED",
            "PRIVATE_MODEL_RUNTIME_NOT_VERIFIED",
            "ENTERPRISE_RAG_RUNTIME_NOT_VERIFIED",
        ],
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "phase3-gate-result.json").write_text(json.dumps(gate_result, indent=2), encoding="utf-8")

    print("PUBLIC_OBSERVABILITY_PASS")
    print("PUBLIC_MYSQL_LOGICAL_PROBE_RESTORE_PASS")
    print("PUBLIC_BACKEND_RESTART_RECOVERY_PASS")
    print("PUBLIC_SBOM_PASS")
    print("PUBLIC_CONTAINER_RISK_BASELINE_AUDITED")
    print("PUBLIC_CONTAINER_EXCEPTIONS_VALIDATED")
    if release_security_blocked:
        print("PUBLIC_RELEASE_SECURITY_BLOCKED")
        print("PUBLIC_OPERATIONS_PHASE3_PARTIAL")
    else:
        print("PUBLIC_OPERATIONS_PHASE3_PASS")
    print("PRODUCTION_READY_NOT_CLAIMED")
    print("PRIVATE_MODEL_RUNTIME_NOT_VERIFIED")
    print("ENTERPRISE_RAG_RUNTIME_NOT_VERIFIED")


if __name__ == "__main__":
    main()
