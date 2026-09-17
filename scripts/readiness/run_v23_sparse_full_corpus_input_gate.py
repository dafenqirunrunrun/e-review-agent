from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "artifacts" / "retrieval-optimization" / "v23-sparse-full-corpus-input-manifest.json"


def main() -> int:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    ok = (
        payload.get("eligibleChunkCount") == 153
        and payload.get("retrievalContentVersion") == "content-only"
        and len(payload.get("rows") or []) == 153
        and all(row.get("contentHash") and row.get("normalizedContentHash") for row in payload.get("rows") or [])
    )
    if ok:
        print("E_REVIEW_V23_SPARSE_FULL_CORPUS_INPUT_PASS")
        return 0
    print("E_REVIEW_V23_SPARSE_FULL_CORPUS_INPUT_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
