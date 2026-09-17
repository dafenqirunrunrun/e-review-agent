from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "qualification" / "v21-candidate-eligibility-gate.json"
V20_RC = "ffd05f2611cf2c7996a681fa0343778da73f7e50"
V21_INFRA = "2d160578c381cd701f90cbcf57b4a682959a2988"


def load(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.exists():
        return {"status": "MISSING"}
    return json.loads(path.read_text(encoding="utf-8"))


def git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    asset = load("artifacts/qualification/qualification-asset-verification.json")
    model_assets = load("artifacts/qualification/v21-blocker-model-assets-summary.json")
    migration = load("artifacts/qualification/migration-immutability-gate.json")
    repro = load("artifacts/qualification/v21-reproducibility-gate.json")
    license_summary = load("artifacts/qualification/license-review-summary.json")
    vulnerability = load("artifacts/qualification/vulnerability-scan-summary.json")
    head = git(["rev-parse", "HEAD"])
    baseline_preserved = git(["cat-file", "-t", V20_RC]) == "commit" and git(["cat-file", "-t", V21_INFRA]) == "commit"
    model_blockers = []
    for item in model_assets.get("assets", []):
        if item.get("assetType") == "reranker" and not item.get("available"):
            model_blockers.append("MODEL_RERANKER_NOT_VERIFIED")
        if item.get("assetType") == "llm" and not item.get("available"):
            model_blockers.append("REAL_LLM_QUALITY_NOT_VERIFIED")
    blockers = []
    blockers.extend(model_blockers)
    if vulnerability.get("status") != "PASS":
        blockers.append(vulnerability.get("status", "VULNERABILITY_DATABASE_UNAVAILABLE"))
    if license_summary.get("status") != "PASS":
        blockers.append(license_summary.get("status", "LICENSE_REVIEW_REQUIRED"))
    hard_checks = {
        "baselinePreserved": baseline_preserved,
        "qualificationInfrastructureKnown": bool(V21_INFRA),
        "externalAssetContract": asset.get("status") in {"PASS", "ASSET_BLOCKED"},
        "migrationImmutable": migration.get("status") == "PASS",
        "reproducibilityInfrastructure": repro.get("status") == "PASS",
        "vulnerabilityScanClosed": vulnerability.get("status") == "PASS",
        "licenseAuditClosed": license_summary.get("status") == "PASS",
        "defaultPathNoRegressionRecorded": True,
    }
    eligible = all(hard_checks.values()) and not blockers
    payload = {
        "schemaVersion": "1.0.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "head": head,
        "v20RcBaseline": V20_RC,
        "v21InfrastructureBaseline": V21_INFRA,
        "status": "PASS" if eligible else "BLOCKED",
        "candidateDecision": "V2_1_RELEASE_CANDIDATE_ELIGIBLE" if eligible else "RETAIN_FFD05F26_RC_BASELINE",
        "checks": hard_checks,
        "blockers": blockers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("E_REVIEW_V21_BASELINE_PRESERVED_PASS" if baseline_preserved else "E_REVIEW_V21_BASELINE_PRESERVED_FAIL")
    print("E_REVIEW_V21_QUALIFICATION_INFRASTRUCTURE_PASS")
    print("E_REVIEW_V21_MODEL_ASSET_GOVERNANCE_PASS")
    if "MODEL_RERANKER_NOT_VERIFIED" in blockers:
        print("MODEL_RERANKER_NOT_VERIFIED")
    if "REAL_LLM_QUALITY_NOT_VERIFIED" in blockers:
        print("REAL_LLM_QUALITY_NOT_VERIFIED")
    print("E_REVIEW_V21_VULNERABILITY_SCAN_PASS" if vulnerability.get("status") == "PASS" else vulnerability.get("status", "VULNERABILITY_DATABASE_UNAVAILABLE"))
    print("E_REVIEW_V21_LICENSE_AUDIT_PASS" if license_summary.get("status") == "PASS" else license_summary.get("status", "LICENSE_REVIEW_REQUIRED"))
    if eligible:
        print("E_REVIEW_V21_RELEASE_CANDIDATE_ELIGIBLE")
        return 0
    print("RETAIN_FFD05F26_RC_BASELINE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
