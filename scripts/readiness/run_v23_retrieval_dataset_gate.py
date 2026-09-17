from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = ROOT / "ai-service"
QUALIFICATION = AI_ROOT / "scripts" / "qualification"
for item in (AI_ROOT, QUALIFICATION):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from v23_retrieval_common import OUT, write_json  # noqa: E402


def main() -> int:
    manifest = read_json(OUT / "v23-retrieval-qualification-v1-manifest.json")
    checks = build_checks(manifest)
    payload = {
        "schemaVersion": "agent-rag-v23-retrieval-dataset-gate-v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "datasetHash": manifest.get("datasetHash", ""),
        "datasetVersion": manifest.get("datasetVersion", ""),
        "forbiddenClaims": ["RETRIEVAL_QUALITY_VERIFIED", "PRODUCTION_RETRIEVAL_PASS"],
    }
    write_json(OUT / "v23-retrieval-dataset-gate.json", payload)
    if payload["status"] == "PASS":
        print("E_REVIEW_V23_RETRIEVAL_DATASET_PASS")
        return 0
    print("E_REVIEW_V23_RETRIEVAL_DATASET_BLOCKED")
    print(json.dumps(checks, ensure_ascii=False, indent=2, sort_keys=True))
    return 1


def build_checks(manifest: dict[str, Any]) -> dict[str, bool]:
    leakage = manifest.get("leakageAudit") or {}
    label_audit = manifest.get("labelAudit") or {}
    negative = manifest.get("negativeCorpusAudit") or {}
    return {
        "manifestPresent": bool(manifest),
        "calibrationAnswerableAtLeast100": (manifest.get("calibrationCounts") or {}).get("answerable", 0) >= 100,
        "calibrationNoAnswerAtLeast25": (manifest.get("calibrationCounts") or {}).get("no_answer", 0) >= 25,
        "evaluationAnswerableAtLeast100": (manifest.get("evaluationCounts") or {}).get("answerable", 0) >= 100,
        "evaluationNoAnswerAtLeast25": (manifest.get("evaluationCounts") or {}).get("no_answer", 0) >= 25,
        "challengeAnswerableAtLeast40": (manifest.get("challengeCounts") or {}).get("answerable", 0) >= 40,
        "challengeNoAnswerAtLeast10": (manifest.get("challengeCounts") or {}).get("no_answer", 0) >= 10,
        "caseFamilyNoCrossSplit": leakage.get("caseFamilyCrossSplitCount") == 0,
        "documentFamilyNoCrossSplit": leakage.get("documentFamilyCrossSplitCount") == 0,
        "oldDiagnosticNoOverlap": leakage.get("oldDiagnosticCaseOverlap") == 0 and leakage.get("oldQueryHashOverlap") == 0,
        "noAnswerCorpusAuditComplete": negative.get("status") == "PASS" and negative.get("checkedNoAnswerCases", 0) >= 60,
        "answerableLabelAuditComplete": label_audit.get("status") == "PASS" and label_audit.get("checkedAnswerableCases", 0) >= 240,
        "allRelevantEvidenceValid": label_audit.get("failureCount") == 0,
        "datasetHashFixed": len(str(manifest.get("datasetHash", ""))) == 64,
        "fullQueryNotStored": all(not case.get("queryStored", True) and "query" not in case for case in manifest.get("cases", [])),
    }


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
