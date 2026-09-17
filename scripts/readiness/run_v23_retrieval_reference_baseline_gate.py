from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-retrieval-reference-baseline-lock.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = (
        p.get("status") == "REFERENCE_BASELINE"
        and p.get("maximumFinalK") == 5
        and p.get("allowBackfill") is False
        and p.get("sparseEnabled") is False
        and p.get("realModelRerankerEnabled") is False
        and p.get("parentAwareEnabled") is False
        and p.get("structuredRepresentationEnabled") is False
    )
    print("E_REVIEW_V23_RETRIEVAL_REFERENCE_BASELINE_LOCK_PASS" if ok else "E_REVIEW_V23_RETRIEVAL_REFERENCE_BASELINE_LOCK_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
