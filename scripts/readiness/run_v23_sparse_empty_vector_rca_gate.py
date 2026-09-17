from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def main() -> int:
    gate = read_json(OUT / "v23-sparse-empty-vector-rca-gate.json")
    if gate.get("status") == "PASS":
        print("E_REVIEW_V23_SPARSE_EMPTY_VECTOR_RCA_COMPLETE")
        return 0
    print("E_REVIEW_V23_SPARSE_EMPTY_VECTOR_RCA_BLOCKED")
    return 1


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
