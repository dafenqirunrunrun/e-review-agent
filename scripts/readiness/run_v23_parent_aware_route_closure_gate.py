from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "retrieval-optimization" / "v23-parent-aware-route-closure.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = (
        p.get("evaluationConsumptionState") == "CONSUMED_BLOCKED"
        and p.get("evaluationRerunAllowed") is False
        and p.get("calibrationRetuningAllowed") is False
        and p.get("challengeAccessed") is False
        and p.get("runtimePromotionAllowed") is False
    )
    print("E_REVIEW_V23_PARENT_AWARE_ROUTE_CLOSED" if ok else "E_REVIEW_V23_PARENT_AWARE_ROUTE_CLOSURE_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
