from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "retrieval-optimization"


def main() -> int:
    analysis = read_json(OUT / "v23-retrieval-miss-case-analysis.json")
    taxonomy = read_json(OUT / "v23-retrieval-miss-taxonomy-summary.json")
    priority = read_json(OUT / "v23-retrieval-optimization-priority-decision.json")
    cases = analysis.get("cases") or []
    checks = {
        "ninetyCasesAnalyzed": analysis.get("diagnosticCases") == 90 and len(cases) == 90,
        "allCasesConsumed": analysis.get("futureQualificationUseAllowed") is False and all(row.get("consumedForFutureQualification") for row in cases),
        "bm25Top100Complete": all("bm25Top100Hit" in row and "bm25BestRelevantRank" in row for row in cases),
        "denseTop100Complete": all("denseTop100Hit" in row and "denseBestRelevantRank" in row for row in cases),
        "rrfTop100Complete": all("rrfTop100Hit" in row and "rrfBestRelevantRank" in row for row in cases),
        "unionOracleComplete": all("unionTop100Hit" in row and "unionBestRelevantRank" in row for row in cases),
        "candidateKDiagnosticComplete": all(row.get("candidateKRequired") for row in cases),
        "eligibilityAuditComplete": all(row.get("eligibilityAudit") for row in cases),
        "indexAuditComplete": all(row.get("indexAudit") for row in cases),
        "chunkAuditComplete": all(row.get("chunkAudit") for row in cases),
        "queryAuditComplete": all(row.get("queryAudit") for row in cases),
        "primaryMissTypePresent": all(row.get("primaryMissType") for row in cases),
        "priorityGenerated": priority.get("status") == "COMPLETE" and bool(priority.get("recommendedPhase")),
        "sensitivePolicyRecorded": taxonomy.get("sensitivePayloadPolicy") == "hashes, ranks, counts, classifications only",
    }
    payload = {
        "schemaVersion": "agent-rag-v23-retrieval-miss-analysis-gate-v1",
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "decision": priority.get("recommendedPhase", ""),
        "qualityClaim": "RETRIEVAL_MISS_ANALYSIS_COMPLETE_NOT_RETRIEVAL_QUALITY_PASS",
    }
    write_json(OUT / "v23-retrieval-miss-analysis-gate.json", payload)
    if payload["status"] == "PASS":
        print("E_REVIEW_V23_RETRIEVAL_MISS_ANALYSIS_COMPLETE")
        return 0
    print("E_REVIEW_V23_RETRIEVAL_MISS_ANALYSIS_BLOCKED")
    print(json.dumps(checks, indent=2, sort_keys=True))
    return 1


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
