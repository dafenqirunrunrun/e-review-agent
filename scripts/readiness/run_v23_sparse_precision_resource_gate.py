from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "artifacts" / "retrieval-optimization" / "v23-sparse-precision-resource-result.json"


def main() -> int:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    gate = payload.get("gate")
    if gate == "E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_PASS":
        print(gate)
        return 0
    if gate == "E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_WARNING":
        print(gate)
        return 0
    print("E_REVIEW_V23_SPARSE_PRECISION_RESOURCE_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
