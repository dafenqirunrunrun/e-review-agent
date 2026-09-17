from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-runtime-trace-configuration.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = all(p.get(k) is True for k in ["defaultTraceDisabled", "defaultReplayDisabled", "defaultPayloadCaptureDisabled", "defaultSinkNone", "qualificationTraceEnabled", "qualificationReplayDisabled", "qualificationPayloadCaptureDisabled"]) and p.get("qualificationSampleRate") == 1.0
    print("E_REVIEW_V24_RUNTIME_TRACE_CONFIGURATION_PASS" if ok else "E_REVIEW_V24_RUNTIME_TRACE_CONFIGURATION_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
