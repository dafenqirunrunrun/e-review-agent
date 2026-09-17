from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "artifacts" / "retrieval-optimization" / "v23-phase-94b-psq-gate.json"


def main() -> int:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    if payload.get("status") == "PASS":
        print("E_REVIEW_V23_PHASE_94B_PSQ_PASS")
        print("E_REVIEW_V23_SPARSE_PRECISION_QUALIFICATION_COMPLETE")
        return 0
    print("E_REVIEW_V23_PHASE_94B_PSQ_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
