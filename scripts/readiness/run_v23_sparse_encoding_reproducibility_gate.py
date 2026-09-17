from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "artifacts" / "retrieval-optimization" / "v23-sparse-process-repeatability.json"


def main() -> int:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    if payload.get("conclusion") == "SPARSE_PROCESS_REPEATABILITY_PASS":
        print("E_REVIEW_V23_SPARSE_ENCODING_REPRODUCIBILITY_PASS")
        return 0
    print("E_REVIEW_V23_SPARSE_ENCODING_REPRODUCIBILITY_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
