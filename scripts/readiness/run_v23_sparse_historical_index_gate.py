from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "artifacts" / "retrieval-optimization" / "v23-sparse-historical-56-reconciliation.json"


def main() -> int:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    decision = payload.get("conclusion")
    if decision == "HISTORICAL_NON_EMPTY_REPRODUCED":
        print("E_REVIEW_V23_SPARSE_HISTORICAL_INDEX_REPRODUCED")
        return 0
    if decision in {"HISTORICAL_NON_EMPTY_NOT_REPRODUCED", "HISTORICAL_CONFIGURATION_INCOMPLETE", "HISTORICAL_NON_EMPTY_SET_NOT_FULLY_IDENTIFIABLE"}:
        print("E_REVIEW_V23_SPARSE_HISTORICAL_INDEX_NON_REPRODUCIBLE")
        return 0
    print("E_REVIEW_V23_SPARSE_HISTORICAL_INDEX_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
