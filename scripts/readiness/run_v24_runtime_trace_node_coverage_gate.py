from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-runtime-trace-node-coverage.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = p.get("requiredNodeCoverageRate") == 1.0 and p.get("retrievalCallCoverageRate") == 1.0 and p.get("modelCallCoverageRate") == 1.0 and p.get("fallbackTransitionCoverageRate") == 1.0
    print("E_REVIEW_V24_RUNTIME_TRACE_NODE_COVERAGE_PASS" if ok else "E_REVIEW_V24_RUNTIME_TRACE_NODE_COVERAGE_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
