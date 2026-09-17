from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-retrieval-runtime-contamination-audit.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = p.get("runtimeContaminationFree") is True and p.get("defaultOff") is True
    print("E_REVIEW_V23_RETRIEVAL_RUNTIME_CONTAMINATION_FREE" if ok else "E_REVIEW_V23_RETRIEVAL_RUNTIME_CONTAMINATION_FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
