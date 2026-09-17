from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-granularity-audit.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    mapped = payload.get("childCount") == 153 and len(payload.get("parentTypes", [])) == payload.get("parentCount")
    if mapped and payload.get("fallbackRootParentCount") == 0 and payload.get("accurateHierarchyLabel"):
        print("E_REVIEW_V23_PARENT_GRANULARITY_AUDIT_PASS")
        return 0
    print("E_REVIEW_V23_PARENT_GRANULARITY_AUDIT_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
