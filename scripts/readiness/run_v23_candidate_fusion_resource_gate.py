from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def main() -> int:
    evaluation = read_json(OUT / "v23-candidate-fusion-evaluation-result.json")
    if evaluation.get("status") != "PASS":
        payload = {"schemaVersion": "agent-rag-v23-candidate-fusion-resource-gate-v1", "status": "BLOCKED", "decision": "EVALUATION_NOT_PASS", "checks": {"evaluationPass": False}}
    else:
        selected = evaluation["selected"]
        baseline = evaluation["baseline"]
        checks = {
            "evaluationPass": True,
            "p95Within135Baseline": selected["latencyP95"] <= baseline["latencyP95"] * 1.35,
            "postFusionCandidateKAtMost50": selected["configuration"]["postFusionCandidateK"] <= 50,
            "maximumFinalKFive": selected["configuration"]["maximumFinalK"] == 5,
        }
        payload = {"schemaVersion": "agent-rag-v23-candidate-fusion-resource-gate-v1", "status": "PASS" if all(checks.values()) else "BLOCKED", "decision": "RESOURCE_QUALIFIED" if all(checks.values()) else "QUALITY_PASS_RESOURCE_BLOCKED", "checks": checks}
    write_json(OUT / "v23-candidate-fusion-resource-result.json", payload)
    print("E_REVIEW_V23_CANDIDATE_FUSION_RESOURCE_PASS" if payload["status"] == "PASS" else "E_REVIEW_V23_CANDIDATE_FUSION_RESOURCE_BLOCKED")
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
