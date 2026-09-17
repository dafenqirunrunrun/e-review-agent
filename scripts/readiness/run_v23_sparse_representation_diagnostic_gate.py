from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "artifacts" / "retrieval-optimization" / "v23-sparse-representation-diagnostic.json"


def main() -> int:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    decision = payload.get("gate", {}).get("decision")
    if decision in {"SPARSE_REPRESENTATION_RESCUE_CANDIDATE_FOUND", "NO_SPARSE_REPRESENTATION_RESCUE_CANDIDATE"}:
        print(decision)
        return 0
    print("SPARSE_REPRESENTATION_DIAGNOSTIC_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
