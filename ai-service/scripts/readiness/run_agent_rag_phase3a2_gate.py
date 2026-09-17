from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
SCRIPTS = AI_ROOT / "scripts"
for path in (AI_ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from agent_rag_phase3a2_common import PHASE3A2_OUT, write_phase3a2_json
from diagnostics.run_bge_m3_embedding_health import run as run_embedding_health
from evaluation.analyze_phase3a2_query_failures import analyze


def run_gate() -> dict:
    health = run_embedding_health()
    analysis = analyze()
    health_pass = health.get("status") == "AGENT_RAG_EMBEDDING_HEALTH_PASS"
    faiss_pass = analysis["faissNumericalCorrectness"]["status"] == "AGENT_RAG_FAISS_NUMERICAL_CORRECTNESS_PASS"
    diagnosis_pass = analysis.get("status") == "AGENT_RAG_DENSE_DIAGNOSIS_PASS"
    no_answer_pass = analysis["noAnswer"]["falseEvidenceRate"] == 0 and analysis["noAnswer"]["noAnswerCorrectRejectionRate"] == 1.0
    fusion_pass = bool(analysis["fusionContribution"]["sampleCount"])
    conclusion = analysis["decision"]["denseQualityConclusion"]
    pass_all = all([health_pass, faiss_pass, diagnosis_pass, no_answer_pass, fusion_pass])
    result = {
        "status": "PASS" if pass_all else "FAIL",
        "denseQualityConclusion": conclusion,
        "embeddingHealth": health_pass,
        "faissNumericalCorrectness": faiss_pass,
        "denseDiagnosis": diagnosis_pass,
        "fusionCalibration": fusion_pass,
        "noAnswerEvidence": no_answer_pass,
        "defaultRetrievalMode": analysis["decision"]["defaultRetrievalMode"],
        "providerType": analysis["providerType"],
        "tokens": _tokens(health_pass, faiss_pass, diagnosis_pass, fusion_pass, no_answer_pass, conclusion, pass_all),
        "evidenceFiles": {
            "embeddingHealth": str(PHASE3A2_OUT / "embedding-health.json"),
            "queryFailureAnalysis": str(PHASE3A2_OUT / "query-failure-analysis.json"),
        },
        "boundaries": [
            "MODEL_RERANKER_NOT_VERIFIED",
            "REAL_LLM_QUALITY_NOT_VERIFIED",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    write_phase3a2_json("phase3a2-gate-result.json", result)
    return result


def _tokens(health: bool, faiss: bool, diagnosis: bool, fusion: bool, no_answer: bool, conclusion: str, pass_all: bool) -> list[str]:
    tokens = []
    if health:
        tokens.append("AGENT_RAG_EMBEDDING_HEALTH_PASS")
    if faiss:
        tokens.append("AGENT_RAG_FAISS_NUMERICAL_CORRECTNESS_PASS")
    if diagnosis:
        tokens.append("AGENT_RAG_DENSE_DIAGNOSIS_PASS")
    if fusion:
        tokens.append("AGENT_RAG_FUSION_CALIBRATION_PASS")
    if no_answer:
        tokens.append("AGENT_RAG_NO_ANSWER_EVIDENCE_PASS")
    tokens.append(conclusion)
    if pass_all:
        tokens.append("AGENT_RAG_PHASE3A2_PASS")
    tokens.extend(["MODEL_RERANKER_NOT_VERIFIED", "REAL_LLM_QUALITY_NOT_VERIFIED", "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED", "NO_PUSH", "NO_TAG", "NO_RELEASE"])
    return tokens


if __name__ == "__main__":
    result = run_gate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    for token in result["tokens"]:
        print(token)
    raise SystemExit(0 if result["status"] == "PASS" else 1)
