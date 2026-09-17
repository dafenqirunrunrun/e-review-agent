from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-resource-result.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    p95_ok = float(payload.get("totalRetrievalP95Ms", 999999)) <= float(payload.get("flatBaselineP95Ms", 0)) * 1.5
    index_ok = float(payload.get("indexSizeRatio", 999999)) <= 1.75
    if payload.get("resourceGatePass") is True and p95_ok and index_ok:
        print("E_REVIEW_V23_PARENT_CHILD_RESOURCE_PASS")
        return 0
    print("E_REVIEW_V23_PARENT_CHILD_RESOURCE_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
