from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-phase-10a-gate.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = payload.get("decision") == "E_REVIEW_V24_PHASE_10A_PASS" and payload.get("phase10bRuntimeTraceIntegrationAllowed") is True
    if ok:
        print("E_REVIEW_V24_PHASE_10A_PASS")
        print("E_REVIEW_V24_AGENT_TRACE_FOUNDATION_QUALIFIED")
        print("E_REVIEW_V24_AGENT_REPLAY_FOUNDATION_QUALIFIED")
        print("PHASE_10B_RUNTIME_TRACE_INTEGRATION_ALLOWED=true")
        return 0
    print("E_REVIEW_V24_PHASE_10A_BLOCKED")
    print("PHASE_10B_RUNTIME_TRACE_INTEGRATION_ALLOWED=false")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
