from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "artifacts" / "agent-productionization"


def main() -> int:
    retrieval = json.loads((BASE / "v24-runtime-trace-real-retrieval.json").read_text(encoding="utf-8"))
    llm = json.loads((BASE / "v24-runtime-trace-real-llm.json").read_text(encoding="utf-8"))
    ok = retrieval.get("realDenseAvailable") is True and llm.get("qwen3Available") is True and llm.get("assetManifestAvailable") is True
    print("E_REVIEW_V24_RUNTIME_TRACE_REAL_MODEL_PASS" if ok else "E_REVIEW_V24_RUNTIME_TRACE_REAL_MODEL_BLOCKED")
    if not retrieval.get("realDenseAvailable"):
        print("BLOCKED:REAL_DENSE_ASSET_UNAVAILABLE")
    if not llm.get("qwen3Available"):
        print("BLOCKED:REAL_LLM_ASSET_UNAVAILABLE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
