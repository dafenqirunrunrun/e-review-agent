from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-runtime-trace-default-boundary.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = p.get("traceEnabledByDefault") is False and p.get("replayEnabledByDefault") is False and p.get("payloadCaptureEnabledByDefault") is False and p.get("traceSinkDefault") == "none" and p.get("sampleRateDefault") == 0.0
    print("E_REVIEW_V24_RUNTIME_TRACE_DEFAULT_BOUNDARY_PASS" if ok else "E_REVIEW_V24_RUNTIME_TRACE_DEFAULT_BOUNDARY_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
