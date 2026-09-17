from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-faiss-runtime-smoke.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    required = ["faissImportPass", "indexBuildPass", "indexSearchPass", "indexReloadPass", "rankingStable", "finiteScores", "expectedTop1Pass"]
    if all(payload.get(key) is True for key in required):
        print("E_REVIEW_V23_FAISS_RUNTIME_PASS")
        return 0
    print("E_REVIEW_V23_FAISS_RUNTIME_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
