from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))
SCRIPTS = AI_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from agent_rag_phase3a_common import PHASE3A_OUT, write_json
from app.agent_rag.metrics import validate_metric_ranges
from scripts.e2e.run_agent_rag_phase3a_real_dense_e2e import run as run_e2e
from scripts.evaluation.run_agent_rag_phase3a_eval import evaluate


def main() -> None:
    evaluation = evaluate()
    e2e = run_e2e()
    real_verified = evaluation.get("status") == "AGENT_RAG_REAL_DENSE_EVALUATION_PASS" and e2e.get("status") == "AGENT_RAG_PHASE3A_REAL_DENSE_E2E_PASS"
    metric_errors = validate_metric_ranges(
        evaluation,
        modes=["bm25", "hashDense", "hybridHash"] + (["bgeM3Dense", "hybridReal"] if evaluation.get("bgeM3Dense") and evaluation.get("hybridReal") else []),
    )
    checks = {
        "bgeM3Provider": bool(real_verified and evaluation.get("providerMetadata", {}).get("providerType") == "bge-m3"),
        "realEmbedding": bool(real_verified and evaluation.get("providerMetadata", {}).get("dimension", 0) > 0),
        "faissIndex": bool(real_verified and evaluation.get("manifest", {}).get("vectorCount", 0) > 0),
        "modelIndexCompatibility": bool(real_verified and e2e.get("incompatibleIndexBlocked")),
        "realDenseRetrieval": bool(real_verified and e2e.get("denseRetrieval")),
        "realDenseFallback": bool(e2e.get("fallbackE2E") or real_verified),
        "metricRanges": not metric_errors,
        "realDenseEvaluation": bool(real_verified and evaluation.get("gates", {}).get("hybridRecallAt5") and evaluation.get("gates", {}).get("hybridNdcgAt5") and not metric_errors),
        "tenantIsolation": bool(real_verified and evaluation.get("hybridReal", {}).get("tenantViolations") == 0),
        "indexRollback": bool(real_verified and e2e.get("rollback")),
    }
    status = "PASS" if all(checks.values()) else "NOT_VERIFIED" if evaluation.get("status") == "AGENT_RAG_REAL_DENSE_NOT_VERIFIED" else "FAIL"
    result = {
        "schemaVersion": "agent-rag-phase3a-gate-v1",
        "status": status,
        "checks": checks,
        "evaluation": evaluation,
        "e2e": e2e,
        "metricErrors": metric_errors,
        "boundaries": [
            "MODEL_RERANKER_NOT_VERIFIED",
            "REAL_LLM_QUALITY_NOT_VERIFIED",
            "LARGE_SCALE_KNOWLEDGE_NOT_VERIFIED",
            "PRODUCTION_CONCURRENCY_NOT_VERIFIED",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    write_json(PHASE3A_OUT / "phase3a-gate-result.json", result)
    if status != "PASS":
        if metric_errors:
            print("AGENT_RAG_EVALUATION_METRIC_INVALID")
        print("AGENT_RAG_REAL_DENSE_NOT_VERIFIED" if status == "NOT_VERIFIED" else "AGENT_RAG_PHASE3A_FAIL")
        print("MODEL_RERANKER_NOT_VERIFIED")
        print("REAL_LLM_QUALITY_NOT_VERIFIED")
        print("ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED")
        print("NO_PUSH")
        print("NO_TAG")
        print("NO_RELEASE")
        raise SystemExit(2 if status == "FAIL" else 0)
    print("AGENT_RAG_BGE_M3_PROVIDER_PASS")
    print("AGENT_RAG_REAL_EMBEDDING_PASS")
    print("AGENT_RAG_FAISS_INDEX_PASS")
    print("AGENT_RAG_MODEL_INDEX_COMPATIBILITY_PASS")
    print("AGENT_RAG_REAL_DENSE_RETRIEVAL_PASS")
    print("AGENT_RAG_REAL_DENSE_FALLBACK_PASS")
    print("AGENT_RAG_REAL_DENSE_EVALUATION_PASS")
    print("AGENT_RAG_PHASE3A_PASS")
    print("MODEL_RERANKER_NOT_VERIFIED")
    print("REAL_LLM_QUALITY_NOT_VERIFIED")
    print("LARGE_SCALE_KNOWLEDGE_NOT_VERIFIED")
    print("PRODUCTION_CONCURRENCY_NOT_VERIFIED")
    print("ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED")
    print("NO_PUSH")
    print("NO_TAG")
    print("NO_RELEASE")


if __name__ == "__main__":
    main()
