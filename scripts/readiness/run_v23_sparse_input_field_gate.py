from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "artifacts" / "retrieval-optimization" / "v23-sparse-model-input-field-audit.json"


def main() -> int:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    gate = payload.get("gate", {})
    if gate.get("status") == "PASS":
        print("E_REVIEW_V23_SPARSE_INPUT_FIELD_AUDIT_PASS")
        return 0
    print("E_REVIEW_V23_SPARSE_INPUT_FIELD_AUDIT_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
