from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.evidence_coverage import PolicyEvidenceCoverageSelector
from app.policy_rag.reranker import PolicyEvidenceReranker
from app.policy_rag.retriever import PolicyEvidenceRetriever
from app.rag_quality.evaluator import evaluate_retrieval_run
from app.rag_quality.models import RagQualityCase, RetrievalHit, RetrievalRunCase
from scripts.run_step242f_after_sales_delta import direct_preferred_metrics


BINDING_DIR = ROOT / "artifacts" / "step242g_after_sales_semantic" / "bound_candidate"
CHUNKS = ROOT / "data" / "policy_rag_real" / "index_step242g_candidate" / "policy_chunks.jsonl"
OUTPUT = ROOT / "artifacts" / "step242g_after_sales_semantic" / "dev_b2_result.json"

DEV_GATES = {
    "candidateEvidenceHitRateAt5": 0.95,
    "riskCoverageAt3": 0.95,
    "directPreferredHitRateAt3": 0.85,
    "citationValidCaseRate": 1.0,
    "noAnswerAbstentionAccuracy": 1.0,
    "unjudgedItemRateAt5": 0.0,
    "duplicateItemRateAt5": 0.0,
}


def main() -> int:
    report = execute_dev()
    write_json(OUTPUT, report)
    print(json.dumps(summary(report), ensure_ascii=False, indent=2))
    return 0 if report["gate"] == "PASS" else 1


def execute_dev() -> dict[str, Any]:
    cases = load_cases(BINDING_DIR / "dev_bound_candidate_v2.jsonl")
    started = time.perf_counter()
    retriever = PolicyEvidenceRetriever.from_jsonl(CHUNKS, enable_dense=True)
    reranker = PolicyEvidenceReranker()
    retriever_readiness = retriever.readiness()
    reranker_readiness = reranker.readiness()
    if retriever_readiness.get("retrievalMode") != "hybrid":
        raise RuntimeError("STEP242G_HYBRID_NOT_READY")
    if not reranker.enabled or reranker_readiness.get("status") != "ready":
        raise RuntimeError("STEP242G_B2_RERANKER_NOT_READY")

    selector = PolicyEvidenceCoverageSelector()
    run_rows: list[RetrievalRunCase] = []
    diagnostics: list[dict[str, Any]] = []
    for case in cases:
        if case.noAnswer:
            run_rows.append(RetrievalRunCase(caseId=case.caseId, abstained=True, metadata={"reason": "EMPTY_UPSTREAM_RISK_HINTS"}))
            continue
        query = evidence_query(case)
        candidates = retriever.search(query, risk_hints=case.riskTypes, top_k=20, mode="hybrid")
        if not candidates or candidates[0].retrieval.get("mode") != "hybrid":
            raise RuntimeError(f"STEP242G_HYBRID_FALLBACK:{case.caseId}")
        preselection = selector.select(candidates, case.riskTypes, limit=5)
        outcome = reranker.rerank(query, preselection.evidence, chunk_resolver=retriever.chunk_for_id)
        if outcome.metadata.get("fallbackUsed") or outcome.metadata.get("effectiveMode") != "hybrid_bge_reranked":
            raise RuntimeError(f"STEP242G_RERANKER_FALLBACK:{case.caseId}")
        postselection = selector.select(outcome.ranked_candidates or outcome.evidence, case.riskTypes, limit=5)
        run_rows.append(
            RetrievalRunCase(
                caseId=case.caseId,
                hits=[
                    RetrievalHit(
                        chunkId=item.chunkId,
                        score=item.score,
                        sourceName=item.sourceName,
                        sourceUrl=item.sourceUrl,
                        sectionPath=item.sectionPath,
                        clauseId=item.clauseId,
                        contentHash=item.contentHash,
                    )
                    for item in postselection.evidence
                ],
                metadata={"variant": "B2", "actualMode": "hybrid", "rerankerMode": "hybrid_bge_reranked"},
            )
        )
        diagnostics.append(
            {
                "caseId": case.caseId,
                "candidateCount": len(candidates),
                "preselection": preselection.metadata,
                "reranker": outcome.metadata,
                "postselection": postselection.metadata,
            }
        )

    evaluation = evaluate_retrieval_run(cases, run_rows, run_name="step242g_after_sales_semantic_dev_b2")
    direct = direct_preferred_metrics(cases, run_rows)
    observed = {**evaluation["metrics"], **{name: value for name, value in direct.items() if isinstance(value, (int, float))}}
    checks = {
        name: float(observed.get(name, -1.0)) == threshold if threshold in {0.0, 1.0} else float(observed.get(name, -1.0)) >= threshold
        for name, threshold in DEV_GATES.items()
    }
    return {
        "schemaVersion": "step242g-after-sales-semantic-dev-v1",
        "gate": "PASS" if all(checks.values()) else "HOLD",
        "scope": "Candidate index only. This Dev result cannot promote a runtime index or authorize the semantic Holdout.",
        "protocol": {
            "name": "current_runtime_b2_hybrid_coverage_rerank",
            "query": "review_text + frozen_after_sales_risk + shared_policy_terms",
            "retrievalCandidateK": 20,
            "coverageCandidateK": 5,
            "rerankerCandidateK": reranker.candidate_k,
            "evidenceLimit": 5,
            "noAnswerPolicy": "abstain_before_retrieval",
        },
        "runtime": {
            "requestedMode": "hybrid",
            "actualMode": "hybrid",
            "retriever": retriever_readiness,
            "reranker": reranker_readiness,
            "durationMs": round((time.perf_counter() - started) * 1000, 2),
        },
        "evaluation": evaluation,
        "directPreferred": direct,
        "devGates": DEV_GATES,
        "devGateChecks": checks,
        "diagnostics": diagnostics,
        "holdoutExecuted": False,
        "limitation": "Single-Codex semantic ground truth for a personal demo; not human gold.",
    }


def evidence_query(case: RagQualityCase) -> str:
    return " ".join(
        [
            case.reviewText[:240],
            " ".join(case.riskTypes),
            "fake review paid incentive conflict of interest review suppression refund after-sales",
        ]
    )


def load_cases(path: Path) -> list[RagQualityCase]:
    return [RagQualityCase.model_validate(json.loads(line)) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "gate": report["gate"],
        "metrics": report["evaluation"]["metrics"],
        "directPreferred": {key: value for key, value in report["directPreferred"].items() if key != "caseResults"},
        "devGateChecks": report["devGateChecks"],
        "holdoutExecuted": report["holdoutExecuted"],
        "runtimeMs": report["runtime"]["durationMs"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
