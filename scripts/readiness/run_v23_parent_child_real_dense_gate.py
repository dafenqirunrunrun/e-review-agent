from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-real-dense-asset-discovery.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    checks = {
        "selected tests": payload.get("selectedTests", 0) > 0,
        "required tests": payload.get("requiredTests", 0) > 0,
        "required passed": payload.get("requiredTestsPassed") == payload.get("requiredTests"),
        "required skipped": payload.get("requiredTestsSkipped") == 0,
        "required failed": payload.get("requiredTestsFailed") == 0,
        "fallback false": payload.get("fallbackUsed") is False,
        "dimension": payload.get("embeddingDimension") == 1024,
        "finite": payload.get("finiteValues") is True,
        "normalized": payload.get("normalized") is True,
        "cuda": payload.get("cudaUsed") is True,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print("E_REVIEW_V23_PARENT_CHILD_REAL_DENSE_BLOCKED")
        for item in failed:
            print(f"FAILED: {item}")
        return 1
    print("E_REVIEW_V23_PARENT_CHILD_REAL_DENSE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
