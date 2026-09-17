from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "artifacts" / "retrieval-optimization" / "v23-sparse-precision-comparison.json"
MATRIX = ROOT / "artifacts" / "retrieval-optimization" / "v23-sparse-precision-stability-matrix.json"


def main() -> int:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    if payload.get("conclusion") and matrix.get("actualRunCount") == 24:
        print("E_REVIEW_V23_SPARSE_PRECISION_STABILITY_PASS")
        return 0
    print("E_REVIEW_V23_SPARSE_PRECISION_STABILITY_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
