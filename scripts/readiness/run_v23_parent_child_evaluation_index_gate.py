from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-evaluation-index-lock.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = (
        payload.get("freshBuild") is True
        and payload.get("oldIndexDependency") is False
        and payload.get("parentFingerprintMatch") is True
        and payload.get("childFingerprintMatch") is True
        and payload.get("bm25FingerprintMatch") is True
        and payload.get("tenantViolations") == 0
        and payload.get("expiredIndexed") == 0
        and payload.get("inactiveIndexed") == 0
    )
    if ok:
        print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_INDEX_PASS")
        return 0
    print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_INDEX_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
