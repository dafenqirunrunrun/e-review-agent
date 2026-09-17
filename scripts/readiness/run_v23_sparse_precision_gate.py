from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "artifacts" / "retrieval-optimization" / "v23-sparse-fp16-fp32-results.json"


def main() -> int:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    decision = payload.get("conclusion")
    if decision in {"SPARSE_PRECISION_PARITY_PASS", "SPARSE_FP16_UNDERFLOW_OR_PRECISION_LOSS_CONFIRMED", "SPARSE_EMPTY_NOT_CAUSED_BY_FP16", "SPARSE_FP32_RESOURCE_BLOCKED"}:
        print(decision)
        return 0
    print("SPARSE_PRECISION_AUDIT_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
