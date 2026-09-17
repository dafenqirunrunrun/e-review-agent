from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-phase-10b-input-lock.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = (
        payload.get("sourceCommit") == "f65ffde8"
        and payload.get("challengeAccessed") is False
        and payload.get("sparseEnabled") is False
        and payload.get("realRerankerEnabled") is False
        and payload.get("parentAwareEnabled") is False
    )
    print("E_REVIEW_V24_PHASE_10B_INPUT_PASS" if ok else "E_REVIEW_V24_PHASE_10B_INPUT_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
