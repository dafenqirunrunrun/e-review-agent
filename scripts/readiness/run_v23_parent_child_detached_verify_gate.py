from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QC2_ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-qc2-detached-verify.json"
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-detached-verify.json"


def main() -> int:
    artifact = QC2_ARTIFACT if QC2_ARTIFACT.exists() else ARTIFACT
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    if payload.get("detachedGate") == "E_REVIEW_V23_PARENT_CHILD_DETACHED_VERIFY_PASS":
        print("E_REVIEW_V23_PARENT_CHILD_DETACHED_VERIFY_PASS")
        return 0
    print("E_REVIEW_V23_PARENT_CHILD_DETACHED_VERIFY_BLOCKED")
    print(payload.get("blockingReason", "DETACHED_VERIFY_INCOMPLETE"))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
