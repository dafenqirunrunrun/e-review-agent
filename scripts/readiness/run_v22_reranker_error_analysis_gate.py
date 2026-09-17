from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "real-model-chain"
DOCS = ROOT / "docs" / "real-model-chain"


def main() -> int:
    case_analysis = read_json(OUT / "v22-reranker-case-level-error-analysis.json")
    truncation = read_json(OUT / "v22-reranker-token-truncation-audit.json")
    taxonomy = read_json(OUT / "v22-reranker-error-taxonomy.json")
    ablation = read_json(OUT / "v22-reranker-input-ablation-summary.json")
    decision = read_json(OUT / "v22-reranker-root-cause-decision.json")
    checks = {
        "diagnosticCaseCount74": case_analysis.get("caseCount") == 74,
        "severeCasesClassified": severe_cases_classified(case_analysis, taxonomy),
        "queryPassageAudited": all_input_audited(case_analysis),
        "truncationAudited": truncation.get("candidateCount", 0) > 0 and "relevantCandidatesTruncated" in truncation,
        "deterministicFeatureAuditPresent": (DOCS / "V22_DETERMINISTIC_RERANKER_FEATURE_AUDIT.md").exists(),
        "chunkLabelMouthAudited": taxonomy.get("caseCount") == 74 and any(key in taxonomy.get("typeCounts", {}) for key in ["LABEL_GRANULARITY_MISMATCH", "PASSAGE_REPRESENTATION_INCOMPLETE", "MODEL_DOMAIN_MISMATCH", "DESTRUCTIVE_REORDERING"]),
        "limitedAblationComplete": bool(ablation.get("stage1PassageRepresentation")) and bool(ablation.get("stage4BatchDeterminism")),
        "rootCauseDecisionPresent": decision.get("decision") in {"RERANKER_RECOVERY_EXPERIMENT_JUSTIFIED", "REAL_RERANKER_MODEL_TASK_MISMATCH", "RERANKER_QUALIFICATION_DATA_BLOCKED", "ROOT_CAUSE_UNRESOLVED"},
        "modelNotVerifiedPreserved": "MODEL_RERANKER_NOT_VERIFIED" in decision.get("boundaries", []),
    }
    payload = {
        "schemaVersion": "agent-rag-v22-reranker-error-analysis-gate-v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "decision": decision.get("decision", ""),
        "forbiddenClaim": "MODEL_RERANKER_VERIFIED",
    }
    write_json(OUT / "v22-reranker-error-analysis-gate.json", payload)
    if payload["status"] == "PASS":
        print("E_REVIEW_V22_RERANKER_ERROR_ANALYSIS_COMPLETE")
        return 0
    print("E_REVIEW_V22_RERANKER_ERROR_ANALYSIS_INCOMPLETE")
    print(json.dumps(checks, indent=2, sort_keys=True))
    return 1


def severe_cases_classified(case_analysis: dict[str, Any], taxonomy: dict[str, Any]) -> bool:
    severe = {row["caseId"] for row in case_analysis.get("cases", []) if row.get("rankingGroup") == "SEVERELY_REGRESSED"}
    classified = {row["caseId"] for row in taxonomy.get("cases", []) if row.get("primaryErrorType")}
    return bool(severe) and severe.issubset(classified)


def all_input_audited(case_analysis: dict[str, Any]) -> bool:
    rows = case_analysis.get("cases", [])
    if not rows:
        return False
    for row in rows:
        if not row.get("queryRepresentationHash") or not row.get("candidateInputAudit"):
            return False
        for item in row.get("candidateInputAudit", []):
            if not item.get("passageRepresentationHash"):
                return False
            if "combinedTokensBeforeTruncation" not in item:
                return False
    return True


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
