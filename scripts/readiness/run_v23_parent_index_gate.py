from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-index-manifest.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    checks = {
        "Parent BM25 Index Complete": payload.get("parentBm25IndexComplete") is True,
        "Parent Dense Index Complete": payload.get("parentDenseIndexComplete") is True,
        "Eligible Parent Count": int(payload.get("eligibleParentCount", 0)) > 0,
        "Missing Parent Count": payload.get("missingParentCount") == 0,
        "Tenant Violations": payload.get("tenantViolations") == 0,
        "Expired Parent Content": payload.get("expiredParentContent") == 0,
        "Content Hash Mismatch": payload.get("contentHashMismatch") == 0,
        "No Real Index Files Stored": payload.get("realIndexFilesStored") is False,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print("E_REVIEW_V23_PARENT_INDEX_BLOCKED")
        for item in failed:
            print(f"FAILED: {item}")
        return 1
    print("E_REVIEW_V23_PARENT_INDEX_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
