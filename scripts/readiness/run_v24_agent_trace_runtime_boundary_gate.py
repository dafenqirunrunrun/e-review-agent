from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-agent-trace-runtime-boundary.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = (
        payload.get("agentTraceEnabledDefault") is False
        and payload.get("agentReplayEnabledDefault") is False
        and payload.get("agentTracePayloadCaptureDefault") is False
        and payload.get("agentTraceSinkDefault") == "none"
    )
    print("E_REVIEW_V24_AGENT_TRACE_RUNTIME_BOUNDARY_PASS" if ok else "E_REVIEW_V24_AGENT_TRACE_RUNTIME_BOUNDARY_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
