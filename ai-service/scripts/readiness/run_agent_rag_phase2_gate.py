from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = ROOT / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from scripts.e2e.run_agent_rag_index_lifecycle_e2e import run as run_lifecycle
from scripts.evaluation.run_agent_rag_phase2_eval import OUT, evaluate


def main() -> None:
    evaluation = evaluate()
    lifecycle = run_lifecycle()
    tolerance = 0.03
    best_single_recall = max(evaluation["bm25"]["recallAt5"], evaluation["dense"]["recallAt5"])
    best_single_mrr = max(evaluation["bm25"]["mrr"], evaluation["dense"]["mrr"])
    checks = {
        "knowledgeContractValid": evaluation["ingestion"]["failedCount"] == 0,
        "ingestion": evaluation["ingestion"]["chunkCount"] > 0 and evaluation["ingestion"]["manifest"]["status"] in {"ready", "active"},
        "hybridQuality": evaluation["hybrid"]["recallAt5"] + tolerance >= best_single_recall and evaluation["hybrid"]["mrr"] + tolerance >= best_single_mrr,
        "tenantIsolation": evaluation["hybrid"]["tenantIsolationViolations"] == 0,
        "timeValidity": evaluation["hybrid"]["expiredEvidenceViolations"] == 0 and evaluation["hybrid"]["inactiveEvidenceViolations"] == 0,
        "evidenceQuality": evaluation["hybrid"]["forbiddenEvidenceViolations"] == 0 and evaluation["hybrid"]["duplicateEvidenceRate"] == 0.0,
        "rerankerFallback": evaluation["hybridReranked"]["rerankerFallbackCorrectness"] == 1.0 and evaluation["hybridReranked"]["ndcgAt5"] + tolerance >= evaluation["hybrid"]["ndcgAt5"],
        "indexActivation": lifecycle["v1SearchOk"] and lifecycle["v2SearchOk"] and lifecycle["v2BeforeActivationDoesNotAffectV1"],
        "indexRollback": lifecycle["rollbackSearchOk"] and lifecycle["manifestIndexVersionInEvidence"],
        "benchmarkCompleted": evaluation["caseCount"] >= 100,
    }
    result = {
        "schemaVersion": "agent-rag-phase2-gate-v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "evaluation": {
            "caseCount": evaluation["caseCount"],
            "bm25RecallAt5": evaluation["bm25"]["recallAt5"],
            "denseRecallAt5": evaluation["dense"]["recallAt5"],
            "hybridRecallAt5": evaluation["hybrid"]["recallAt5"],
            "hybridMrr": evaluation["hybrid"]["mrr"],
            "hybridNdcgAt5": evaluation["hybrid"]["ndcgAt5"],
            "rerankedNdcgAt5": evaluation["hybridReranked"]["ndcgAt5"],
            "citationCoverage": evaluation["hybrid"]["citationCoverage"],
            "tenantViolations": evaluation["hybrid"]["tenantIsolationViolations"],
            "expiredEvidenceViolations": evaluation["hybrid"]["expiredEvidenceViolations"],
            "duplicateRate": evaluation["hybrid"]["duplicateEvidenceRate"],
        },
        "latency": evaluation["latency"],
        "qualityTolerance": {
            "hybridMrrTolerance": tolerance,
            "reason": "fixture_hash_dense_mode_rank_variance_not_real_embedding_quality",
        },
        "lifecycle": lifecycle,
        "boundaries": [
            "MODEL_RERANKER_QUALITY_NOT_CLAIMED",
            "LARGE_SCALE_KNOWLEDGE_NOT_VERIFIED",
            "ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED",
            "NO_PUSH",
            "NO_TAG",
            "NO_RELEASE",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "phase2-gate-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result["status"] != "PASS":
        raise SystemExit(json.dumps(result, ensure_ascii=False, indent=2))
    print("AGENT_RAG_KNOWLEDGE_CONTRACT_PASS")
    print("AGENT_RAG_INGESTION_PASS")
    print("AGENT_RAG_HYBRID_RETRIEVAL_PASS")
    print("AGENT_RAG_RERANKER_FALLBACK_PASS")
    print("AGENT_RAG_EVIDENCE_QUALITY_PASS")
    print("AGENT_RAG_INDEX_LIFECYCLE_PASS")
    print("AGENT_RAG_INDEX_ROLLBACK_PASS")
    print("AGENT_RAG_PHASE2_PASS")
    print("MODEL_RERANKER_QUALITY_NOT_CLAIMED")
    print("LARGE_SCALE_KNOWLEDGE_NOT_VERIFIED")
    print("ENTERPRISE_RAG_PRODUCTION_NOT_CLAIMED")
    print("NO_PUSH")
    print("NO_TAG")
    print("NO_RELEASE")


if __name__ == "__main__":
    main()
