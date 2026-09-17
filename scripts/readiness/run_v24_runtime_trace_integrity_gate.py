from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "artifacts" / "agent-productionization" / "v24-runtime-trace-integrity.json"


def main() -> int:
    p = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    ok = p.get("normalTraces") == p.get("completeTraces") and all(p.get(k) == 0 for k in ["incompleteTraces", "hashFailures", "sequenceGaps", "orphanSpans", "footerMismatches"])
    print("E_REVIEW_V24_RUNTIME_TRACE_INTEGRITY_PASS" if ok else "E_REVIEW_V24_RUNTIME_TRACE_INTEGRITY_BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
