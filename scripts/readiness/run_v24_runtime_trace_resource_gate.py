from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-runtime-trace-resource.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = p.get("p95TraceSizeBytes", 999999) <= 128 * 1024 and p.get("pythonMemoryDeltaMb", 999) <= 64 and p.get("javaMemoryDeltaMb", 999) <= 64 and p.get("traceWriteFailureCount") == 0
    print("E_REVIEW_V24_RUNTIME_TRACE_RESOURCE_PASS" if ok else "RUNTIME_TRACE_QUALITY_PASS_RESOURCE_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
