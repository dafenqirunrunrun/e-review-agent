from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-retrieval-challenge-preservation.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = (
        p.get("challengeCaseCount") == 75
        and p.get("challengeQueryHashesRead") is False
        and p.get("challengeLabelsRead") is False
        and p.get("challengeRetrievalExecuted") is False
        and p.get("challengeMetricsGenerated") is False
        and p.get("preservedForFutureIndependentResearch") is True
    )
    print("E_REVIEW_V23_RETRIEVAL_CHALLENGE_PRESERVED" if ok else "E_REVIEW_V23_RETRIEVAL_CHALLENGE_PRESERVATION_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
