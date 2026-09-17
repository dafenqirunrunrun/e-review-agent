from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-runtime-trace-context-isolation.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = p.get("traceContamination") == 0 and p.get("executionContamination") == 0 and p.get("requestContamination") == 0 and p.get("orphanEvents") == 0 and p.get("wrongParentSpans") == 0
    print("E_REVIEW_V24_RUNTIME_TRACE_CONTEXT_ISOLATION_PASS" if ok else "E_REVIEW_V24_RUNTIME_TRACE_CONTEXT_ISOLATION_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
