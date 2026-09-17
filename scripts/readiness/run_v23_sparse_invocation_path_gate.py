from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "artifacts" / "retrieval-optimization" / "v23-sparse-invocation-path-diff.json"


def main() -> int:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    if payload.get("gate", {}).get("status") == "PASS":
        print("E_REVIEW_V23_SPARSE_INVOCATION_PATH_PASS")
        return 0
    print("E_REVIEW_V23_SPARSE_INVOCATION_PATH_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
