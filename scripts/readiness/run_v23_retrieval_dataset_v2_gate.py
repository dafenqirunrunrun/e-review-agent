from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def main() -> int:
    audit = read_json(OUT / "v23-retrieval-qualification-v2-audit.json")
    manifest = read_json(OUT / "v23-retrieval-qualification-v2-manifest.json")
    split_counts = manifest.get("splitLabelCounts", {})
    checks = {
        "datasetVersionV2": manifest.get("datasetVersion") == "v23-retrieval-qualification-v2",
        "totalCases375": manifest.get("caseCount") == 375,
        "calibration120Answerable30NoAnswer": split_counts.get("calibration", {}).get("answerable") == 120 and split_counts.get("calibration", {}).get("no_answer") == 30,
        "evaluation120Answerable30NoAnswer": split_counts.get("evaluation", {}).get("answerable") == 120 and split_counts.get("evaluation", {}).get("no_answer") == 30,
        "challenge60Answerable15NoAnswer": split_counts.get("challenge", {}).get("answerable") == 60 and split_counts.get("challenge", {}).get("no_answer") == 15,
        "oldQueryLeakageZero": audit.get("oldQueryHashIntersectionCount") == 0,
        "oldCaseLeakageZero": audit.get("oldCaseIdIntersectionCount") == 0,
        "caseFamilyLeakageZero": audit.get("caseFamilyLeakageCount") == 0,
        "documentFamilyLeakageZero": audit.get("documentFamilyLeakageCount") == 0,
        "answerableLabelAuditComplete": audit.get("answerableLabelAuditComplete") is True,
        "noAnswerCorpusAuditComplete": audit.get("noAnswerCorpusAuditComplete") is True,
        "intentDistributionSpreadAtMost010": audit.get("intentMaxSpread", 1.0) <= 0.10,
        "difficultyDistributionSpreadAtMost020": audit.get("difficultyMaxSpread", 1.0) <= 0.20,
    }
    payload = {
        "schemaVersion": "agent-rag-v23-retrieval-dataset-v2-gate-v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "datasetHash": manifest.get("datasetHash"),
    }
    write_json(OUT / "v23-retrieval-qualification-v2-gate.json", payload)
    print("E_REVIEW_V23_RETRIEVAL_DATASET_V2_PASS" if payload["status"] == "PASS" else "E_REVIEW_V23_RETRIEVAL_DATASET_V2_BLOCKED")
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
