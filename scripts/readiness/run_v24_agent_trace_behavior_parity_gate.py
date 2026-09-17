from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-agent-trace-behavior-parity.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    cases = payload.get("syntheticCases")
    ok = (
        cases == 30
        and payload.get("businessOutcomeMatches") == cases
        and payload.get("nodeSequenceMatches") == cases
        and payload.get("fallbackDecisionMatches") == cases
    )
    print("E_REVIEW_V24_AGENT_TRACE_BEHAVIOR_PARITY_PASS" if ok else "E_REVIEW_V24_AGENT_TRACE_BEHAVIOR_PARITY_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
