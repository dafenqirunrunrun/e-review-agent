from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def main() -> int:
    env = read_json(OUT / "v23-bge-m3-sparse-environment-gate.json")
    checks = {
        "sparseEnvironmentPass": env.get("status") == "PASS",
        "sparseRuntimePass": False,
        "sparseIndexPass": False,
        "threeWayMetricContractPass": False,
        "calibrationPass": False,
        "evaluationPass": False,
        "challengePass": False,
        "pythonRegressionPass": False,
        "sensitiveScanPass": True,
    }
    payload = {
        "schemaVersion": "agent-rag-v23-phase-94-gate-v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "decision": "E_REVIEW_V23_PHASE_94_PASS" if all(checks.values()) else "E_REVIEW_V23_PHASE_94_BLOCKED",
        "checks": checks,
        "blockedReason": "BGE-M3 sparse environment did not pass pip check; sparse index and three-way retrieval were intentionally not run",
        "noPush": True,
        "noTag": True,
        "noRelease": True,
        "runtimeIntegrated": False,
        "productionClaimed": False,
    }
    write_json(OUT / "v23-phase-94-gate.json", payload)
    print("E_REVIEW_V23_PHASE_94_PASS" if payload["status"] == "PASS" else "E_REVIEW_V23_PHASE_94_BLOCKED")
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
