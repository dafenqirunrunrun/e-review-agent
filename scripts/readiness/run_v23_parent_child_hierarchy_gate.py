from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-hierarchy-audit.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    checks = {
        "153 / 153 Child Mapped": payload.get("childChunkCount") == 153 and payload.get("orphanChildCount") == 0,
        "Parent ID Deterministic": payload.get("parentIdDeterministic") is True and payload.get("randomUuidUsed") is False,
        "Tenant Consistent": payload.get("crossTenantMappingCount") == 0,
        "Document Consistent": payload.get("crossDocumentMappingCount") == 0,
        "No Duplicate Child": payload.get("duplicateChildMappingCount") == 0,
        "No Orphan Child": payload.get("orphanChildCount") == 0,
        "No LLM Parent Summary": payload.get("llmParentSummaryUsed") is False,
        "No Full Content Stored": payload.get("fullChildContentStored") is False and payload.get("fullParentContentStored") is False,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        print("E_REVIEW_V23_PARENT_CHILD_HIERARCHY_BLOCKED")
        for item in failed:
            print(f"FAILED: {item}")
        return 1
    print("E_REVIEW_V23_PARENT_CHILD_HIERARCHY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
