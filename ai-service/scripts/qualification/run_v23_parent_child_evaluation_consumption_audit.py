from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, AI_ROOT / "scripts", QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from v23_parent_child_heldout_common import OUT, consumption_audit_payload, write_json  # noqa: E402


def main() -> int:
    payload = consumption_audit_payload()
    write_json(OUT / "v23-parent-child-evaluation-consumption-audit.json", payload)
    print(payload["evaluationConsumptionStatus"])
    return 0 if payload["evaluationConsumptionStatus"] == "EVALUATION_SPLIT_UNCONSUMED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
