from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def main() -> int:
    decision = read_json(OUT / "v23-candidate-fusion-calibration-decision.json")
    results = read_json(OUT / "v23-candidate-fusion-calibration-results.json")
    checks = {
        "decisionPass": decision.get("status") == "PASS",
        "validDecision": decision.get("decision") in {"VALID_EQUAL_WEIGHT_RRF_CONFIGURATION", "VALID_WEIGHTED_RRF_CONFIGURATION"},
        "calibrationOnly": results.get("stage1Count", 0) > 0,
        "selectedConfigPresent": bool((decision.get("selected") or {}).get("configurationHash")),
        "maximumFinalKFive": ((decision.get("selected") or {}).get("configuration") or {}).get("maximumFinalK") == 5,
        "postFusionCandidateKAtMost50": ((decision.get("selected") or {}).get("configuration") or {}).get("postFusionCandidateK", 999) <= 50,
    }
    payload = {"schemaVersion": "agent-rag-v23-candidate-fusion-calibration-gate-v1", "status": "PASS" if all(checks.values()) else "BLOCKED", "checks": checks, "decision": decision.get("decision", "")}
    write_json(OUT / "v23-candidate-fusion-calibration-gate.json", payload)
    print("E_REVIEW_V23_CANDIDATE_FUSION_CALIBRATION_PASS" if payload["status"] == "PASS" else "E_REVIEW_V23_CANDIDATE_FUSION_CALIBRATION_BLOCKED")
    return 0 if payload["status"] == "PASS" else 1


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
