from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "artifacts" / "operations" / "v1.9.0-phase3"
RUNTIME_EVIDENCE = ROOT / "artifacts" / "runtime" / "v1.9.0-phase2"


def _exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def main() -> None:
    checks = {
        "PUBLIC_OBSERVABILITY_PASS": _exists(RUNTIME_EVIDENCE / "observability-smoke-summary.json"),
        "PUBLIC_BACKUP_RESTORE_PASS": _exists(RUNTIME_EVIDENCE / "backup-restore-smoke-summary.json"),
        "PUBLIC_CONTAINER_SECURITY_PASS": _exists(EVIDENCE / "container-security-summary.json"),
        "PUBLIC_SBOM_PASS": _exists(EVIDENCE / "sbom" / "manifest.json"),
        "PUBLIC_ROLLBACK_PASS": _exists(RUNTIME_EVIDENCE / "rollback-smoke-summary.json"),
    }
    result = {
        "checks": checks,
        "boundaries": [
            "PRODUCTION_READY_NOT_CLAIMED",
            "PRIVATE_MODEL_RUNTIME_NOT_VERIFIED",
            "ENTERPRISE_RAG_RUNTIME_NOT_VERIFIED",
        ],
    }
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "phase3-gate-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    failed = [name for name, ok in checks.items() if not ok]
    for name, ok in checks.items():
        if ok:
            print(name)
    print("PRODUCTION_READY_NOT_CLAIMED")
    print("PRIVATE_MODEL_RUNTIME_NOT_VERIFIED")
    print("ENTERPRISE_RAG_RUNTIME_NOT_VERIFIED")
    if failed:
        raise SystemExit("PUBLIC_OPERATIONS_PHASE3_BLOCKED: " + ", ".join(failed))
    print("PUBLIC_OPERATIONS_PHASE3_PASS")


if __name__ == "__main__":
    main()
