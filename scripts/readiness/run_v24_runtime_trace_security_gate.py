from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-runtime-trace-security.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = all(
        p.get(k) == 0
        for k in [
            "queryLeaks",
            "promptLeaks",
            "evidenceLeaks",
            "modelResponseLeaks",
            "secretLeaks",
            "authorizationLeaks",
            "absolutePathLeaks",
        ]
    )
    print("E_REVIEW_V24_RUNTIME_TRACE_SECURITY_PASS" if ok else "E_REVIEW_V24_RUNTIME_TRACE_SECURITY_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
