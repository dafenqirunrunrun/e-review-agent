from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-agent-trace-security-result.json"


def main() -> int:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = (
        payload.get("rawQueryLeakCount") == 0
        and payload.get("rawPromptLeakCount") == 0
        and payload.get("rawEvidenceLeakCount") == 0
        and payload.get("rawToolArgumentLeakCount") == 0
        and payload.get("secretLeakCount") == 0
        and payload.get("absolutePathLeakCount") == 0
        and payload.get("payloadCaptureDisabledByDefault") is True
    )
    print("E_REVIEW_V24_AGENT_TRACE_SECURITY_PASS" if ok else "E_REVIEW_V24_AGENT_TRACE_SECURITY_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
