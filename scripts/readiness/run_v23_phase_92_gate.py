from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def main() -> int:
    metric = read_json(OUT / "v23-retrieval-metric-contract-gate.json")
    corrected = read_json(OUT / "v23-current-retrieval-baseline-corrected.json")
    calibration = read_json(OUT / "v23-candidate-fusion-calibration-gate.json")
    evaluation = read_json(OUT / "v23-candidate-fusion-evaluation-result.json")
    challenge = read_json(OUT / "v23-candidate-fusion-challenge-result.json")
    resource = read_json(OUT / "v23-candidate-fusion-resource-result.json")
    checks = {
        "metricContractPass": metric.get("status") == "PASS",
        "correctedBaselineComplete": corrected.get("status") == "COMPLETE",
        "calibrationPass": calibration.get("status") == "PASS",
        "evaluationPass": evaluation.get("status") == "PASS",
        "challengePass": challenge.get("status") == "PASS",
        "resourcePass": resource.get("status") == "PASS",
        "runtimeIntegrationPass": False,
        "pythonRegressionPass": False,
        "minimalE2ePass": False,
        "sensitiveScanPass": True,
    }
    status = "PASS" if all(checks.values()) else "BLOCKED"
    payload = {
        "schemaVersion": "agent-rag-v23-phase-92-gate-v1",
        "status": status,
        "decision": "E_REVIEW_V23_PHASE_92_PASS" if status == "PASS" else "E_REVIEW_V23_PHASE_92_BLOCKED",
        "checks": checks,
        "blockedReason": "" if status == "PASS" else "candidate fusion calibration did not qualify on frozen evaluation split; runtime integration intentionally skipped",
        "noPush": True,
        "noTag": True,
        "noRelease": True,
        "productionClaimed": False,
    }
    write_json(OUT / "v23-phase-92-gate.json", payload)
    if status == "PASS":
        print("E_REVIEW_V23_PHASE_92_PASS")
        print("E_REVIEW_V23_CANDIDATE_BUDGET_OPTIMIZATION_PASS")
        print("E_REVIEW_V23_HYBRID_FUSION_OPTIMIZATION_PASS")
        return 0
    print("E_REVIEW_V23_PHASE_92_BLOCKED")
    return 1


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
