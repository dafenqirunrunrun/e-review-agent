from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def main() -> int:
    gate = read_json(OUT / "v23-bge-m3-sparse-environment-gate.json")
    status = gate.get("status")
    if status == "PASS":
        print("E_REVIEW_V23_BGE_M3_SPARSE_ISOLATED_ENVIRONMENT_PASS")
        print("E_REVIEW_V23_BGE_M3_SPARSE_ENVIRONMENT_PASS")
        print("AGENT_RAG_V23_REAL_BGE_M3_SPARSE_RUNTIME_PASS")
        return 0
    print("E_REVIEW_V23_BGE_M3_SPARSE_ENVIRONMENT_BLOCKED")
    return 1


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
