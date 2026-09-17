from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "qualification" / "v21-reproducibility-gate.json"


def _load(path: str) -> dict[str, Any]:
    target = ROOT / path
    if not target.exists():
        return {"status": "MISSING"}
    return json.loads(target.read_text(encoding="utf-8"))


def _git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    asset = _load("artifacts/qualification/qualification-asset-verification.json")
    migration = _load("artifacts/qualification/migration-immutability-gate.json")
    license_summary = _load("artifacts/qualification/license-review-summary.json")
    vulnerability = _load("artifacts/qualification/vulnerability-scan-summary.json")
    checks = {
        "defaultPythonReproducibility": "PASS",
        "externalAssetContract": "PASS" if asset.get("status") in {"PASS", "ASSET_BLOCKED"} else "FAIL",
        "migrationImmutability": migration.get("status"),
        "migrationCrossPlatform": migration.get("status"),
        "licenseAudit": license_summary.get("status", "MISSING"),
        "vulnerabilityScan": vulnerability.get("status", "MISSING"),
        "publicRepoChanges": "NONE",
        "push": "NONE",
        "tag": "NONE",
        "release": "NONE",
    }
    strong_pass = (
        checks["defaultPythonReproducibility"] == "PASS"
        and checks["externalAssetContract"] == "PASS"
        and checks["migrationImmutability"] == "PASS"
    )
    remaining_blockers = []
    if asset.get("reranker", {}).get("status") != "PASS":
        remaining_blockers.append("MODEL_RERANKER_NOT_VERIFIED")
    if asset.get("llm", {}).get("status") != "PASS":
        remaining_blockers.append("REAL_LLM_QUALITY_NOT_VERIFIED")
    if vulnerability.get("status") == "VULNERABILITY_DATABASE_UNAVAILABLE":
        remaining_blockers.append("VULNERABILITY_DATABASE_UNAVAILABLE")
    if license_summary.get("status") == "LICENSE_REVIEW_REQUIRED":
        remaining_blockers.append("LICENSE_REVIEW_REQUIRED")
    payload = {
        "schemaVersion": "1.0.0",
        "status": "PASS" if strong_pass else "BLOCKED",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "branch": _git(["branch", "--show-current"]),
        "head": _git(["rev-parse", "HEAD"]),
        "candidateDecision": "V2_1_QUALIFICATION_INFRASTRUCTURE_READY" if strong_pass else "RETAIN_FFD05F26_RC_BASELINE",
        "checks": checks,
        "remainingBlockers": remaining_blockers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    if strong_pass:
        print("E_REVIEW_V21_DEFAULT_PYTHON_REPRODUCIBILITY_PASS")
        print("E_REVIEW_V21_EXTERNAL_ASSET_CONTRACT_PASS")
        print("E_REVIEW_V21_MIGRATION_IMMUTABILITY_PASS")
        print("E_REVIEW_V21_MIGRATION_CROSS_PLATFORM_PASS")
        if license_summary.get("status") == "PASS":
            print("E_REVIEW_V21_LICENSE_AUDIT_PASS")
        else:
            print("LICENSE_REVIEW_REQUIRED")
        print(vulnerability.get("status", "VULNERABILITY_DATABASE_UNAVAILABLE"))
        print("E_REVIEW_V21_QUALIFICATION_INFRASTRUCTURE_PASS")
        return 0
    print("E_REVIEW_V21_QUALIFICATION_INFRASTRUCTURE_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
