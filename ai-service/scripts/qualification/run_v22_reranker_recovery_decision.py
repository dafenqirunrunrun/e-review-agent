from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts" / "real-model-chain"


def main() -> int:
    manifest = read_json(OUT / "v22-reranker-benchmark-manifest.json")
    calibration = read_json(OUT / "v22-reranker-calibration-decision.json")
    evaluation = read_json(OUT / "v22-real-reranker-benchmark-summary.json")
    harness = read_json(OUT / "v22-reranker-harness-audit.json")
    case_analysis = read_json(OUT / "v22-reranker-regression-case-analysis.json")
    no_answer_cases = int((evaluation.get("categoryCounts") or {}).get("no-answer") or 0)
    false_evidence = int(evaluation.get("falseEvidenceCount") or 0)
    no_answer_false_evidence = no_answer_cases * int((evaluation.get("selected") or {}).get("finalK") or 0)
    invariant = {
        "finalK": (evaluation.get("selected") or {}).get("finalK"),
        "evaluationNoAnswerCases": no_answer_cases,
        "expectedNoAnswerFalseEvidenceIfAlwaysTopK": no_answer_false_evidence,
        "observedFalseEvidenceCount": false_evidence,
        "observedFalseEvidenceFullyExplainedByNoAnswerTopK": false_evidence == no_answer_false_evidence,
        "runtimeHasNoRejectThreshold": runtime_has_no_reject_threshold(),
        "benchmarkRequiresFalseEvidenceZero": True,
    }
    status = "BLOCKED"
    payload = {
        "schemaVersion": "agent-rag-v22-reranker-recovery-calibration-decision-v1",
        "createdAtUtc": now(),
        "status": status,
        "sourceCommit": "57858817",
        "benchmark": {
            "benchmarkHash": manifest.get("benchmarkHash"),
            "knowledgeHash": manifest.get("knowledgeHash"),
            "calibrationHash": manifest.get("calibrationHash"),
            "evaluationHash": manifest.get("evaluationHash"),
        },
        "currentModel": {
            "modelId": "BAAI/bge-reranker-v2-m3",
            "revision": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e",
        },
        "currentSelectedConfiguration": evaluation.get("selected") or calibration.get("selected"),
        "testedEvidence": {
            "scoreDirectionPass": True,
            "flagEmbeddingTransformersParityPass": True,
            "harnessAuditStatus": harness.get("status"),
            "originalCalibrationGridCount": calibration.get("gridCount"),
            "originalEvaluationCaseCount": evaluation.get("caseCount"),
        },
        "safetyInvariant": invariant,
        "qualityMetrics": {
            "deterministicSemanticNdcgAt5": evaluation.get("deterministicSemanticNdcgAt5"),
            "realSemanticNdcgAt5": evaluation.get("realSemanticNdcgAt5"),
            "deterministicSemanticMrr": evaluation.get("deterministicSemanticMrr"),
            "realSemanticMrr": evaluation.get("realSemanticMrr"),
            "deterministicOverallNdcgAt5": evaluation.get("deterministicOverallNdcgAt5"),
            "realOverallNdcgAt5": evaluation.get("realOverallNdcgAt5"),
            "deterministicOverallMrr": evaluation.get("deterministicOverallMrr"),
            "realOverallMrr": evaluation.get("realOverallMrr"),
            "expiredEvidenceLeaks": evaluation.get("expiredEvidenceLeaks"),
            "falseEvidenceCount": evaluation.get("falseEvidenceCount"),
            "noAnswerCorrectRejection": evaluation.get("noAnswerCorrectRejection"),
        },
        "caseRootCauseCounts": case_analysis.get("rootCauseCounts"),
        "decision": "AGENT_RAG_V22_REAL_RERANKER_QUALITY_REGRESSION",
        "modelBoundary": "MODEL_RERANKER_NOT_VERIFIED",
        "blockedReasons": [
            "NO_ANSWER_REJECTION_THRESHOLD_NOT_IMPLEMENTED",
            "FALSE_EVIDENCE_ZERO_CANNOT_BE_REACHED_BY_DTYPE_OR_CANDIDATEK_ONLY",
            "REAL_SEMANTIC_METRICS_REMAIN_BELOW_DETERMINISTIC_BASELINE",
            "EVALUATION_ALREADY_OBSERVED_AND_MUST_NOT_BE_USED_FOR_MORE_PARAMETER_SEARCH",
        ],
        "nextSafeChange": "Implement a separate calibrated no-answer/rejection policy on calibration data in a future phase, then freeze before one evaluation run.",
    }
    write_json(OUT / "v22-reranker-recovery-calibration-decision.json", payload)
    print("AGENT_RAG_V22_REAL_RERANKER_RECOVERY_BLOCKED")
    print("MODEL_RERANKER_NOT_VERIFIED")
    return 2


def runtime_has_no_reject_threshold() -> bool:
    text = (ROOT / "ai-service" / "app" / "agent_rag" / "reranker.py").read_text(encoding="utf-8")
    threshold_terms = ["reject_threshold", "min_reranker_score", "no_answer_threshold"]
    return not any(term in text for term in threshold_terms)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
