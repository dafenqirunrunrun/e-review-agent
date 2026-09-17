from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-child-evaluation-split-isolation.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if payload.get("splitIsolationPass") is True:
        print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_SPLIT_ISOLATION_PASS")
        return 0
    print("E_REVIEW_V23_PARENT_CHILD_EVALUATION_SPLIT_ISOLATION_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
