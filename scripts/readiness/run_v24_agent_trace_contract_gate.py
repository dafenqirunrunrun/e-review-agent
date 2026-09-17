from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-agent-trace-contract.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = (
        payload.get("schemaVersion") == "agent-trace.v1"
        and "EXECUTION_STARTED" in payload.get("eventTypes", [])
        and "EXTERNAL_TOOL" in payload.get("nodeTypes", [])
        and "SUCCEEDED" in payload.get("statusTypes", [])
        and payload.get("idContract", {}).get("idsDerivedFromPayload") is False
    )
    print("E_REVIEW_V24_AGENT_TRACE_CONTRACT_PASS" if ok else "E_REVIEW_V24_AGENT_TRACE_CONTRACT_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
