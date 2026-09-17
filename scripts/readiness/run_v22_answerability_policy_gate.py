from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "artifacts" / "real-model-chain" / "v22-evidence-answerability-calibration-decision.json"
OUT = ROOT / "artifacts" / "real-model-chain" / "v22-answerability-policy-gate.json"


def main() -> int:
    decision = json.loads(DECISION.read_text(encoding="utf-8")) if DECISION.exists() else {}
    valid = decision.get("decision") in {"VALID_DETERMINISTIC_POLICY", "VALID_CALIBRATED_POLICY"}
    payload = {
        "schemaVersion": "agent-rag-v22-answerability-policy-gate-v1",
        "status": "PASS" if valid else "BLOCKED",
        "decision": decision.get("decision") or "MISSING_ANSWERABILITY_DECISION",
        "policyType": decision.get("policyType") or "none",
        "runtimeIntegrationAllowed": valid,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if valid:
        print("E_REVIEW_V22_ANSWERABILITY_CALIBRATION_PASS")
        print("E_REVIEW_V22_NO_ANSWER_REJECTION_PASS")
        return 0
    print(payload["decision"])
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
